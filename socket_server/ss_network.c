#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>

#include "ss_network.h"

int
resolve(struct sockaddr *ia, int pf, const char *host,
  const char *servname, int flags)
{
    int n;
    struct addrinfo hints, *res;

    memset(&hints, 0, sizeof(hints));
    hints.ai_flags = flags;          /* We create listening sockets */
    hints.ai_family = pf;              /* Protocol family */
    hints.ai_socktype = SOCK_DGRAM;     /* UDP */

    n = getaddrinfo(host, servname, &hints, &res);
    if (n == 0) {
        /* Use the first socket address returned */
        memcpy(ia, res->ai_addr, res->ai_addrlen);
        freeaddrinfo(res);
    }

    return n;
}

int
local4remote(struct sockaddr *ra, struct sockaddr_storage *la)
{
    int s, r;
    socklen_t llen;

    s = socket(ra->sa_family, SOCK_DGRAM, 0);
    if (s == -1) {
        return (-1);
    }
    if (connect(s, ra, SA_LEN(ra)) == -1) {
        close(s);
        return (-1);
    }
    llen = sizeof(*la);
    r = getsockname(s, sstosa(la), &llen);
    close(s);
    return (r);
}

double
getdtime(void)
{
    struct timeval timev;

    if (gettimeofday(&timev, NULL) == -1)
        return -1;

    return timev.tv_sec + ((double)timev.tv_usec) / 1000000.0;
}

char *
addr2char_r(struct sockaddr *ia, char *buf, int size)
{
    void *addr;

    switch (ia->sa_family) {
    case AF_INET:
        addr = &(satosin(ia)->sin_addr);
        break;

    case AF_INET6:
        addr = &(satosin6(ia)->sin6_addr);
        break;

    default:
        abort();
    }

    return (char *)((void *)inet_ntop(ia->sa_family, addr, buf, size));
}

const char *
addr2char(struct sockaddr *ia)
{
    static char buf[256];

    return(addr2char_r(ia, buf, sizeof(buf)));
}
