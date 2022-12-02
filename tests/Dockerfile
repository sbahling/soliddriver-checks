FROM opensuse/leap:latest

WORKDIR /root

RUN zypper --non-interactive in python39 python39-pip kmod
RUN zypper --non-interactive dup

RUN pip3.9 install rich pdfkit pandas \
openpyxl click paramiko dominate build

# easy for rebuild and install, source_codes is created in 
# create_container_***.sh
RUN echo "cd source_codes" > build_install.sh
RUN echo "python3.9 -m build" >> build_install.sh
RUN echo "python3.9 setup.py install" >> build_install.sh
RUN chmod +x build_install.sh

