#ifndef _SS_LTHREAD_H_
#define _SS_LTHREAD_H_

#include <pthread.h>

struct lthread_args
{
    char *listen_addr;
    int listen_port;
    int sock;
    struct wi *inpacket_queue;
    struct wi *inpacket_queue_tail;
    pthread_cond_t inpacket_queue_cond;
    pthread_mutex_t inpacket_queue_mutex;
    struct wi *outpacket_queue;
    struct wi *outpacket_queue_tail;
    pthread_cond_t outpacket_queue_cond;
    pthread_mutex_t outpacket_queue_mutex;
};

#define INP(xp) ((xp)->body.inp)
#define OUTP(xp) ((xp)->body.outp)

enum wi_type {WI_INPACKET, WI_OUTPACKET};

struct inpacket_wi
{
    char *databuf;
    int rsize;
    double dtime;
    char *remote_addr;
    int remote_port;
    char *local_addr;
    int local_port;
};

struct outpacket_wi
{
    char *databuf;
    int ssize;
    char *remote_addr;
    char *remote_port;
    char *local_addr;
    int local_port;
};

struct wi
{
    enum wi_type wi_type;
    union {
        struct inpacket_wi inp;
        struct outpacket_wi outp;
    } body;
    struct wi  *next;
};

void queue_put_item(struct wi *wi, struct wi **queue, struct wi **queue_tail,
  pthread_mutex_t *queue_mutex, pthread_cond_t *queue_cond);
struct wi *wi_malloc(enum wi_type type);
void wi_free(struct wi *wi);

#endif
