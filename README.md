# Sippy B2BUA
Sippy B2BUA is a [RFC3261](https://www.ietf.org/rfc/rfc3261.txt)-compliant
Session Initiation Protocol (SIP)
(Back-to-back user agent)[http://en.wikipedia.org/wiki/Back-to-back_user_agent]i
(B2BUA). 

The Sippy B2BUA is a SIP call controlling component. Unlike a SIP proxy server,
which only maintains transaction state, the Sippy B2BUA maintains complete call
state and participates in all call requests. For this reason it can perform
number of functions that are not possible to implement using SIP proxy, such
as for example accurate call accounting, pre-paid rating and billing, fail
over call routing etc. Unlike PBX-type solutions such as Asterisk for example,
the Sippy B2BUA doesn't perform any media relaying or processing, therefore it
doesn't introduce any additional packet loss, delay or jitter into the
media path. 

## Features

- 5,000-10,000 simultaneous sessions per server;
- 150-400 call setups/tear-downs per second;
- Real-time calls control and call data records (CDRs) generation;
- Optional ability to use (Sippy RTPproxy)[https://github.com/sippy/rtpproxy] for media relaying;
- Optional ability to perform Cisco-compatible RADIUS AAA (Authentication,
Authorization and Accounting);
- RFC3261 compliance;
- Seamless compatibility with majority of popular SIP software and hardware on
the market today;
- Robustness and Resilience;
- Simple and clean, yet flexible, internal design making implementing new
features and services easy;
- Sippy B2BUA could be easily combined with other Open Source software, such as
SIP Express Router / OpenSIPS to build complete softswitch solution.

## Installation

`pip install git+https://github.com/sippy/b2bua`

## Running

To get started, you can use the b2bua_simple implementation. The following example will cause the b2bua run in the foreground so you can see the SIP messaging. If you make a call to the IP address of your host machine, the b2bua will recieve the call on its UAC side, and it will send a new call leg out its UAS side to the IP address 192.168.1.1. It is expected that 192.168.1.1 is some sort of SIP switch or termination gateway.

`b2bua_simple -f -n 192.168.1.1`

