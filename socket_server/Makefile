# $Id: Makefile,v 1.11 2010/05/21 16:30:12 sobomax Exp $

DISTVERSION=	0.2
DISTFILES=	GNUmakefile Makefile

PROG=	socket_server
SRCS=	main.c ss_network.c b2bua_socket.c ss_lthread.c ss_util.c ss_base64.c \
	ss_queue.c
SRCS+=	b2bua_socket.h ss_base64.h ss_lthread.h ss_network.h ss_util.h \
	ss_queue.h ss_defines.h
DISTFILES+=	${SRCS}
DISTNAME=	${PROG}-${DISTVERSION}
DISTOUTFILE=	${DISTNAME}.tar.bz2
MAN1=

WARNS?=	2

LOCALBASE?=	/usr/local
BINDIR?=	${LOCALBASE}/bin

CFLAGS=	-g3 -O0 -Wall -I${LOCALBASE}/include
LDADD+=	-lpthread -L${LOCALBASE}/lib -liksemel

distfile:
	rm -rf ${DISTNAME}
	mkdir -p ${DISTNAME}
	cp ${DISTFILES} ${DISTNAME}/
	tar -cvy -f ${DISTOUTFILE} ${DISTNAME}/
	rm -rf ${DISTNAME}

.include <bsd.prog.mk>
