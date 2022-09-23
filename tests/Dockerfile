FROM opensuse/leap:latest

WORKDIR /root

RUN zypper --non-interactive in python3-pip kmod

RUN pip3 install rich pdfkit pandas \
openpyxl click paramiko dominate build

