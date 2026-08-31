#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main() {
    printf("==========================================\n");
    printf("      ZEROSPACE C SANDBOX TEST UTILITY   \n");
    printf("==========================================\n");
    
    char* userprofile = getenv("USERPROFILE");
    char* temp = getenv("TEMP");
    char* path = getenv("PATH");
    
    printf("USERPROFILE: %s\n", userprofile ? userprofile : "NOT SET");
    printf("TEMP: %s\n", temp ? temp : "NOT SET");
    printf("PATH: %s\n", path ? path : "NOT SET");
    
    if (userprofile && strstr(userprofile, "containers") != NULL) {
        printf("\n[SUCCESS] Environment folders isolated inside ZeroSpace containers!\n");
    } else {
        printf("\n[WARNING] USERPROFILE does not contain 'containers'.\n");
    }
    return 0;
}
