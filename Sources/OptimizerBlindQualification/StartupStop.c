#include <unistd.h>

__attribute__((constructor)) static void stop_after_loading(void) {
    _exit(0);
}
