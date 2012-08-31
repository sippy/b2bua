#ifndef _SS_LTHREAD_H_
#define _SS_LTHREAD_H_

#include <pthread.h>

struct lthread_args
{
    char *listen_addr;
    int listen_port;
    struct inpacket_wi *inpacket_queue;
    struct inpacket_wi *inpacket_queue_tail;
    pthread_cond_t inpacket_queue_cond;
    pthread_mutex_t inpacket_queue_mutex;
};

struct inpacket_wi
{
    char *databuf;
    int rsize;
    double dtime;
    char *remote_addr;
    int remote_port;
    char *local_addr;
    int local_port;
    struct inpacket_wi *next;
};

#endif
