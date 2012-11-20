# $Id: Makefile,v 1.11 2010/05/21 16:30:12 sobomax Exp $

PROG=	socket_server
SRCS=	main.c ss_network.c b2bua_socket.c ss_lthread.c ss_util.c ss_base64.c
MAN1=

WARNS?=	2

LOCALBASE?=	/usr/local
BINDIR?=	${LOCALBASE}/bin

CFLAGS=	-g3 -O0 -Wall -I${LOCALBASE}/include
LDADD+=	-lpthread -L${LOCALBASE}/lib -liksemel

.include <bsd.prog.mk>
