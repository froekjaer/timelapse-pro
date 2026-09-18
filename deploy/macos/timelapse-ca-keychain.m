/*
 * TimeLapse Pro — Headend API mTLS CA keychain helper.
 *
 * This command-line helper deliberately uses the SecItem API. For a launchd
 * daemon outside a GUI user context, SecItem targets the file-based keychain;
 * the production item is provisioned in /Library/Keychains/System.keychain.
 *
 * Purposefully narrow interface:
 *   --read   write the exact passphrase bytes to stdout for Headend only
 *   --probe  verify non-interactive read access without exposing the secret
 *
 * The service/account are compile-time constants. There is no caller-
 * controlled item selection. The executable is installed root-owned so the
 * runtime user cannot replace the binary trusted by the file-based ACL.
 */
#import <Foundation/Foundation.h>
#import <LocalAuthentication/LocalAuthentication.h>
#import <Security/Security.h>
#include <pwd.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#define KEYCHAIN_SERVICE "dk.froekjaer.timelapse.headend-api-mtls-ca"
#define KEYCHAIN_ACCOUNT "timelapse-headend"
#define HEADEND_RUNTIME_USER "peter"

static int caller_is_allowed(void) {
    uid_t uid = geteuid();
    if (uid == 0) {
        return 1;
    }
    struct passwd *pw = getpwnam(HEADEND_RUNTIME_USER);
    return pw != NULL && uid == pw->pw_uid;
}

static int read_secret(int probe_only) {
    if (!caller_is_allowed()) {
        fputs("timelapse-ca-keychain: caller not permitted\n", stderr);
        return 77;
    }

    @autoreleasepool {
        LAContext *context = [[LAContext alloc] init];
        context.interactionNotAllowed = YES;

        /*
         * Explicitly keep this on the file-based keychain implementation.
         * The LaunchDaemon has no Data Protection Keychain user context.
         * The production item is created only in System.keychain and uses a
         * unique service/account pair.
         */
        NSDictionary *query = @{
            (__bridge id)kSecClass: (__bridge id)kSecClassGenericPassword,
            (__bridge id)kSecAttrService: @KEYCHAIN_SERVICE,
            (__bridge id)kSecAttrAccount: @KEYCHAIN_ACCOUNT,
            (__bridge id)kSecReturnData: @YES,
            (__bridge id)kSecMatchLimit: (__bridge id)kSecMatchLimitOne,
            (__bridge id)kSecUseDataProtectionKeychain: @NO,
            (__bridge id)kSecUseAuthenticationContext: context,
        };

        CFTypeRef result = NULL;
        OSStatus status = SecItemCopyMatching(
            (__bridge CFDictionaryRef)query,
            &result
        );
        if (status != errSecSuccess || result == NULL) {
            if (result != NULL) {
                CFRelease(result);
            }
            fprintf(
                stderr,
                "timelapse-ca-keychain: passphrase unavailable (%d)\n",
                (int)status
            );
            return 66;
        }

        if (CFGetTypeID(result) != CFDataGetTypeID()) {
            CFRelease(result);
            fputs("timelapse-ca-keychain: unexpected keychain result\n", stderr);
            return 65;
        }

        CFDataRef secret = (CFDataRef)result;
        CFIndex secret_len = CFDataGetLength(secret);
        const UInt8 *secret_data = CFDataGetBytePtr(secret);
        if (secret_len <= 0 || secret_data == NULL) {
            CFRelease(result);
            fputs("timelapse-ca-keychain: empty passphrase\n", stderr);
            return 66;
        }

        int rc = 0;
        if (probe_only) {
            if (fputs("OK\n", stdout) == EOF) {
                rc = 74;
            }
        } else {
            if (
                fwrite(secret_data, 1, (size_t)secret_len, stdout)
                != (size_t)secret_len
            ) {
                rc = 74;
            }
        }
        if (fflush(stdout) != 0) {
            rc = 74;
        }

        CFRelease(result);
        return rc;
    }
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fputs("usage: timelapse-ca-keychain --read|--probe\n", stderr);
        return 64;
    }
    if (strcmp(argv[1], "--read") == 0) {
        return read_secret(0);
    }
    if (strcmp(argv[1], "--probe") == 0) {
        return read_secret(1);
    }
    fputs("usage: timelapse-ca-keychain --read|--probe\n", stderr);
    return 64;
}
