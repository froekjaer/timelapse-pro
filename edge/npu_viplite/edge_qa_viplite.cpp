#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <iterator>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>
#include <unistd.h>

#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

extern "C" {
#include <awnn_lib.h>
}

namespace {

const char* kLabels[] = {
    "ok",
    "blurry",
    "depth_of_field_issue",
    "snow_or_dirt_on_lens",
    "condensation",
    "direct_sun_reflection",
    "underexposed",
    "overexposed",
    "white_balance_cast",
};

struct Args {
    std::string model;
    std::string image;
    std::string input_layout = "nhwc_rgb";
    std::string input_dtype = "fp16";
    int width = 224;
    int height = 224;
    int classes = 9;
    bool json = false;
};

class StdoutToStderr {
public:
    StdoutToStderr() {
        saved_stdout_ = dup(STDOUT_FILENO);
        if (saved_stdout_ >= 0) {
            fflush(stdout);
            dup2(STDERR_FILENO, STDOUT_FILENO);
        }
    }

    ~StdoutToStderr() {
        if (saved_stdout_ >= 0) {
            fflush(stdout);
            dup2(saved_stdout_, STDOUT_FILENO);
            close(saved_stdout_);
        }
    }

    StdoutToStderr(const StdoutToStderr&) = delete;
    StdoutToStderr& operator=(const StdoutToStderr&) = delete;

private:
    int saved_stdout_ = -1;
};

std::string json_escape(const std::string& value) {
    std::string out;
    out.reserve(value.size() + 8);
    for (char c : value) {
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\b': out += "\\b"; break;
            case '\f': out += "\\f"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (static_cast<unsigned char>(c) < 0x20) {
                    char buf[8];
                    std::snprintf(buf, sizeof(buf), "\\u%04x", c);
                    out += buf;
                } else {
                    out += c;
                }
        }
    }
    return out;
}

uint16_t float_to_fp16(float value) {
    uint32_t bits;
    std::memcpy(&bits, &value, sizeof(bits));

    const uint32_t sign = (bits >> 16) & 0x8000u;
    int32_t exponent = static_cast<int32_t>((bits >> 23) & 0xffu) - 127 + 15;
    uint32_t mantissa = bits & 0x7fffffu;

    if (exponent <= 0) {
        if (exponent < -10) {
            return static_cast<uint16_t>(sign);
        }
        mantissa = (mantissa | 0x800000u) >> (1 - exponent);
        return static_cast<uint16_t>(sign | ((mantissa + 0x1000u) >> 13));
    }

    if (exponent >= 31) {
        return static_cast<uint16_t>(sign | 0x7c00u);
    }

    return static_cast<uint16_t>(sign | (static_cast<uint32_t>(exponent) << 10) | ((mantissa + 0x1000u) >> 13));
}

void write_fp16(std::vector<uint8_t>& out, size_t index, float value) {
    const uint16_t half = float_to_fp16(value);
    out[index * 2] = static_cast<uint8_t>(half & 0xffu);
    out[index * 2 + 1] = static_cast<uint8_t>((half >> 8) & 0xffu);
}

void usage(const char* argv0) {
    std::cerr
        << "Usage: " << argv0 << " --model edge_qa.nb --image image.jpg --json "
        << "[--input-layout nhwc_rgb|nchw_rgb|nchw_bgr] [--input-dtype fp16|uint8] [--classes 9]\n";
}

Args parse_args(int argc, char** argv) {
    Args args;
    for (int i = 1; i < argc; ++i) {
        std::string key(argv[i]);
        auto next = [&]() -> std::string {
            if (i + 1 >= argc) {
                throw std::runtime_error("Missing value for " + key);
            }
            return std::string(argv[++i]);
        };
        if (key == "--model") args.model = next();
        else if (key == "--image") args.image = next();
        else if (key == "--input-layout") args.input_layout = next();
        else if (key == "--input-dtype") args.input_dtype = next();
        else if (key == "--width") args.width = std::stoi(next());
        else if (key == "--height") args.height = std::stoi(next());
        else if (key == "--classes") args.classes = std::stoi(next());
        else if (key == "--json") args.json = true;
        else if (key == "--help" || key == "-h") {
            usage(argv[0]);
            std::exit(0);
        } else {
            throw std::runtime_error("Unknown argument: " + key);
        }
    }
    if (args.model.empty()) throw std::runtime_error("--model is required");
    if (args.image.empty()) throw std::runtime_error("--image is required");
    if (args.classes < 1 || args.classes > static_cast<int>(std::size(kLabels))) {
        throw std::runtime_error("--classes must be 1..9");
    }
    if (args.input_layout != "nhwc_rgb" && args.input_layout != "nchw_rgb" && args.input_layout != "nchw_bgr") {
        throw std::runtime_error("--input-layout must be nhwc_rgb, nchw_rgb or nchw_bgr");
    }
    if (args.input_dtype != "fp16" && args.input_dtype != "uint8") {
        throw std::runtime_error("--input-dtype must be fp16 or uint8");
    }
    return args;
}

std::vector<uint8_t> preprocess(const Args& args) {
    cv::Mat bgr = cv::imread(args.image, cv::IMREAD_COLOR);
    if (bgr.empty()) {
        throw std::runtime_error("Could not read image: " + args.image);
    }
    cv::Mat resized;
    cv::resize(bgr, resized, cv::Size(args.width, args.height), 0, 0, cv::INTER_AREA);

    cv::Mat rgb;
    cv::cvtColor(resized, rgb, cv::COLOR_BGR2RGB);

    const size_t pixels = static_cast<size_t>(args.width) * static_cast<size_t>(args.height);
    const bool use_uint8 = args.input_dtype == "uint8";
    std::vector<uint8_t> out(pixels * 3 * (use_uint8 ? sizeof(uint8_t) : sizeof(uint16_t)));
    float input_scale = 1.0f / 255.0f;
    if (const char* env_scale = std::getenv("TIMELAPSE_EDGE_QA_INPUT_SCALE")) {
        input_scale = std::strtof(env_scale, nullptr);
    }

    auto write_value = [&](size_t index, uint8_t raw) {
        if (use_uint8) {
            out[index] = raw;
        } else {
            write_fp16(out, index, static_cast<float>(raw) * input_scale);
        }
    };

    for (int y = 0; y < args.height; ++y) {
        const uint8_t* row = rgb.ptr<uint8_t>(y);
        for (int x = 0; x < args.width; ++x) {
            const size_t p = static_cast<size_t>(y) * args.width + x;
            const uint8_t r = row[x * 3 + 0];
            const uint8_t g = row[x * 3 + 1];
            const uint8_t b = row[x * 3 + 2];
            if (args.input_layout == "nhwc_rgb") {
                write_value(p * 3, r);
                write_value(p * 3 + 1, g);
                write_value(p * 3 + 2, b);
            } else if (args.input_layout == "nchw_rgb") {
                write_value(p, r);
                write_value(pixels + p, g);
                write_value(pixels * 2 + p, b);
            } else {
                write_value(p, b);
                write_value(pixels + p, g);
                write_value(pixels * 2 + p, r);
            }
        }
    }
    return out;
}

std::vector<float> softmax_first_n(const float* raw, int count) {
    std::vector<float> probs(count);
    float maxv = raw[0];
    for (int i = 1; i < count; ++i) maxv = std::max(maxv, raw[i]);
    double sum = 0.0;
    for (int i = 0; i < count; ++i) {
        probs[i] = std::exp(raw[i] - maxv);
        sum += probs[i];
    }
    if (sum <= 0.0) sum = 1.0;
    for (float& p : probs) p = static_cast<float>(p / sum);
    return probs;
}

void emit_json(const Args& args, const std::vector<float>& raw, const std::vector<float>& scores) {
    int top = 0;
    for (int i = 1; i < args.classes; ++i) {
        if (scores[i] > scores[top]) top = i;
    }
    std::cout << "{";
    std::cout << "\"engine\":\"edge_qa_viplite_aw_nn_v1\",";
    std::cout << "\"available\":true,";
    std::cout << "\"label\":\"" << kLabels[top] << "\",";
    std::cout << "\"class_id\":" << top << ",";
    std::cout << "\"confidence\":" << scores[top] << ",";
    std::cout << "\"model_path\":\"" << json_escape(args.model) << "\",";
    std::cout << "\"input_layout\":\"" << json_escape(args.input_layout) << "\",";
    std::cout << "\"input_dtype\":\"" << json_escape(args.input_dtype) << "\",";
    std::cout << "\"scores\":{";
    for (int i = 0; i < args.classes; ++i) {
        if (i) std::cout << ",";
        std::cout << "\"" << kLabels[i] << "\":" << scores[i];
    }
    std::cout << "},\"raw_first_n\":{";
    for (int i = 0; i < args.classes; ++i) {
        if (i) std::cout << ",";
        std::cout << "\"" << kLabels[i] << "\":" << raw[i];
    }
    std::cout << "}}";
    std::cout << std::endl;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        Args args = parse_args(argc, argv);
        std::vector<float> raw(args.classes);
        std::vector<float> scores;
        {
            StdoutToStderr redirect_vendor_logs;
            std::vector<uint8_t> input = preprocess(args);
            void* input_buffers[] = {input.data()};

            awnn_init();
            Awnn_Context_t* context = awnn_create(args.model.c_str());
            if (!context) {
                awnn_uninit();
                throw std::runtime_error("awnn_create returned null");
            }
            awnn_set_input_buffers(context, input_buffers);
            awnn_run(context);
            float** outputs = awnn_get_output_buffers(context);
            if (!outputs || !outputs[0]) {
                awnn_destroy(context);
                awnn_uninit();
                throw std::runtime_error("awnn_get_output_buffers returned null");
            }
            for (int i = 0; i < args.classes; ++i) raw[i] = outputs[0][i];
            scores = softmax_first_n(outputs[0], args.classes);
            awnn_destroy(context);
            awnn_uninit();
        }

        emit_json(args, raw, scores);
        return 0;
    } catch (const std::exception& exc) {
        std::cout << "{"
                  << "\"engine\":\"edge_qa_viplite_aw_nn_v1\","
                  << "\"available\":false,"
                  << "\"error\":\"" << json_escape(exc.what()) << "\""
                  << "}" << std::endl;
        return 2;
    }
}
