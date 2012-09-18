#ifndef _SS_LTHREAD_H_
#define _SS_LTHREAD_H_

#include <pthread.h>

struct queue
{
    struct wi *head;
    struct wi *tail;
    pthread_cond_t cond;
    pthread_mutex_t mutex;
    int length;
};

struct lthread_args
{
    char *listen_addr;
    int listen_port;
    int sock;
    struct queue outpacket_queue;
    int recvonly;
    struct b2bua_slot *bslots;
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

void queue_put_item(struct wi *wi, struct queue *);
struct wi *wi_malloc(enum wi_type type);
void wi_free(struct wi *wi);
void lthread_mgr_run(struct lthread_args *args);
struct wi *queue_get_item(struct queue *queue, int return_on_wake);

#endif
