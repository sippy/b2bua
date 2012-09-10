#ifndef _SS_NETWORK_H_
#define _SS_NETWORK_H_

#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>

#if !defined(SA_LEN)
#define SA_LEN(sa) \
  (((sa)->sa_family == AF_INET) ? \
  sizeof(struct sockaddr_in) : sizeof(struct sockaddr_in6))
#endif
#if !defined(SS_LEN)
#define SS_LEN(ss) \
  (((ss)->ss_family == AF_INET) ? \
  sizeof(struct sockaddr_in) : sizeof(struct sockaddr_in6))
#endif

#if !defined(satosin)
#define satosin(sa)     ((struct sockaddr_in *)(sa))
#endif
#if !defined(satosin6)
#define satosin6(sa)    ((struct sockaddr_in6 *)(sa))
#endif
#if !defined(sstosa)
#define sstosa(ss)      ((struct sockaddr *)(ss))
#endif

int resolve(struct sockaddr *, int, const char *, const char *, int);
int local4remote(struct sockaddr *, struct sockaddr_storage *);
double getdtime(void);
char *addr2char_r(struct sockaddr *, char *, int);
const char *addr2char(struct sockaddr *);

#endif
