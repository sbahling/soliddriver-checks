FROM opensuse/leap:latest

RUN zypper --non-interactive in kmod python39 python39-pip
RUN pip3.9 install soliddriver-checks

EXPOSE 8080
ENV REFRESH_INTERVAL=12

ENTRYPOINT ["soliddriver-checks-service"]

