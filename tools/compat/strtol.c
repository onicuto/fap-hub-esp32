#include <stdlib.h>

long strtol(const char *nptr, char **endptr, int base) {
    const char *s = nptr;
    while (*s == ' ' || *s == '\t' || *s == '\n' || *s == '\r' || *s == '\f' || *s == '\v') {
        s++;
    }
    int neg = 0;
    if (*s == '-') {
        neg = 1;
        s++;
    } else if (*s == '+') {
        s++;
    }
    unsigned long val = strtoul(s, endptr, base);
    if (endptr && *endptr == s && s != nptr) {
        *endptr = (char *)nptr;
    }
    return neg ? -(long)val : (long)val;
}
