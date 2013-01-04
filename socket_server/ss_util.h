#ifndef _SS_UTIL_H_
#define _SS_UTIL_H_

#include <stddef.h>
#include <stdint.h>

struct app_cfg;

struct str
{
    int len;
    char *s;
};

typedef struct str str;

uint32_t ss_crc32(const void *buf, size_t size);
uint32_t hash_string(str *, int);
int ss_daemon(int nochdir, int redirect_fd);
int drop_privileges(struct app_cfg *);

#endif
