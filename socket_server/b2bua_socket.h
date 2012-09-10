#ifndef _B2BUA_SOCKET_H_
#define _B2BUA_SOCKET_H_

#include "ss_lthread.h"
#include "ss_util.h"

struct b2bua_xchg_args;

struct b2bua_slot
{
    int id;
    struct queue inpacket_queue;
    struct b2bua_slot *next;
};

void b2bua_acceptor_run(struct lthread_args *);
struct b2bua_slot *b2bua_getslot(struct b2bua_slot *bslots, str *call_id);
struct b2bua_slot *b2bua_getslot_by_id(struct b2bua_slot *bslots, int id);

#endif
