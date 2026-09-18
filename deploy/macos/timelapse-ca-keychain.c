/*
 * TimeLapse Pro — Headend API mTLS CA System-keychain helper.
 *
 * Purposefully narrow interface:
 *   --read   write the exact passphrase bytes to stdout for Headend only
 *   --probe  verify non-interactive read access without exposing the secret
 *
 * The service/account and System keychain path are compile-time constants.
 * There is no caller-controlled item selection. The executable is installed
 * root-owned so the runtime user cannot replace the binary trusted by the
 * file-based keychain ACL.
 */
#include <CoreFoundation/CoreFoundation.h>
#include <Security/Security.h>
#include <pwd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define SYSTEM_KEYCHAIN_PATH "/Library/Keychains/System.keychain"
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

    /* Never permit an authentication UI from the boot-time daemon path. */
    OSStatus status = SecKeychainSetUserInteractionAllowed(false);
    if (status != errSecSuccess) {
        fprintf(stderr, "timelapse-ca-keychain: cannot disable UI (%d)\n", (int)status);
        return 70;
    }

    SecKeychainRef keychain = NULL;
    status = SecKeychainOpen(SYSTEM_KEYCHAIN_PATH, &keychain);
    if (status != errSecSuccess || keychain == NULL) {
        fprintf(stderr, "timelapse-ca-keychain: cannot open System keychain (%d)\n", (int)status);
        return 69;
    }

    UInt32 secret_len = 0;
    void *secret_data = NULL;
    status = SecKeychainFindGenericPassword(
        keychain,
        (UInt32)strlen(KEYCHAIN_SERVICE), KEYCHAIN_SERVICE,
        (UInt32)strlen(KEYCHAIN_ACCOUNT), KEYCHAIN_ACCOUNT,
        &secret_len, &secret_data,
        NULL
    );
    CFRelease(keychain);

    if (status != errSecSuccess || secret_data == NULL || secret_len == 0) {
        if (secret_data != NULL) {
            SecKeychainItemFreeContent(NULL, secret_data);
        }
        fprintf(stderr, "timelapse-ca-keychain: passphrase unavailable (%d)\n", (int)status);
        return 66;
    }

    int rc = 0;
    if (probe_only) {
        if (fputs("OK\n", stdout) == EOF) {
            rc = 74;
        }
    } else {
        if (fwrite(secret_data, 1, secret_len, stdout) != secret_len) {
            rc = 74;
        }
    }
    if (fflush(stdout) != 0) {
        rc = 74;
    }

    SecKeychainItemFreeContent(NULL, secret_data);
    return rc;
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
