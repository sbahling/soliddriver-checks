FROM opensuse/leap:latest

WORKDIR /root

RUN zypper --non-interactive in python39 python39-pip kmod
RUN zypper --non-interactive dup

RUN pip3.9 install rich pdfkit pandas \
openpyxl click paramiko dominate build

