# Build stage
FROM python:3.9-slim-bullseye AS builder

ENV NUT_VERSION=2.8.2

# Combine all build commands in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
        libusb-1.0-0-dev \
        build-essential \
        wget \
        libssl-dev \
        libneon27-dev \
        libsnmp-dev \
        libtool \
        autoconf \
        automake \
        libgd-dev \
        pkg-config && \
    cd /tmp && \
    wget https://www.networkupstools.org/source/2.8/nut-$NUT_VERSION.tar.gz && \
    tar xfz nut-$NUT_VERSION.tar.gz && \
    cd nut-$NUT_VERSION && \
    ./configure \
        --prefix=/usr \
        --sysconfdir=/etc/nut \
        --disable-dependency-tracking \
        --enable-strip \
        --disable-static \
        --with-all=no \
        --with-usb=yes \
        --with-openssl \
        --with-dev \
        --with-serial \
        --with-snmp \
        --with-neon \
        --with-ipv6 \
        --with-cgi \
        --with-nutclient \
        --with-drivers=usbhid-ups,nutdrv_qx,blazer_usb,blazer_ser,snmp-ups,richcomm_usb,tripplite_usb,riello_usb \
        --datadir=/usr/share/nut \
        --with-drvpath=/usr/share/nut \
        --with-statepath=/var/run/nut \
        --with-user=nut \
        --with-group=nut && \
    make && \
    make install DESTDIR=/tmp/install && \
    # Create directories for optional files
    mkdir -p /tmp/install/usr/bin /tmp/install/usr/lib/nut /tmp/install/usr/include /tmp/install/usr/lib/pkgconfig && \
    # Create empty files for optional components to ensure COPY doesn't fail
    touch /tmp/install/usr/bin/nut-scanner && \
    touch /tmp/install/usr/lib/libnutscan.so && \
    touch /tmp/install/usr/lib/libnutclient.so && \
    touch /tmp/install/usr/include/nutclient.h && \
    touch /tmp/install/usr/include/nut-scan.h && \
    touch /tmp/install/usr/include/nut_version.h && \
    touch /tmp/install/usr/include/parseconf.h && \
    touch /tmp/install/usr/include/upsclient.h && \
    touch /tmp/install/usr/lib/pkgconfig/libnutclient.pc && \
    touch /tmp/install/usr/lib/pkgconfig/libnutscan.pc && \
    touch /tmp/install/usr/lib/pkgconfig/libupsclient.pc && \
    # Clean up unnecessary files
    find /tmp/install -name "*.a" -delete && \
    find /tmp/install -name "*.la" -delete && \
    # Clean up build dependencies to reduce layer size
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /tmp/nut-$NUT_VERSION && \
    rm -f /tmp/nut-$NUT_VERSION.tar.gz

# Python dependencies stage
FROM python:3.9-slim-bullseye AS python-deps
WORKDIR /app
COPY nutify/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.9-slim-bullseye

# Combine all setup commands in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
        libusb-1.0-0 \
        msmtp \
        openssl \
        ca-certificates \
        libsnmp40 \
        libneon27 \
        libgd3 \
        procps \
        net-tools \
        iputils-ping \
        socat \
        libudev-dev \
        usbutils \
        lsof \
        iproute2 && \
    # Create nut user and group
    groupadd -g 1000 nut && \
    useradd -r -u 1000 -g nut -d /var/run/nut -s /sbin/nologin nut && \
    # Ensure nut user has access to USB devices
    usermod -a -G plugdev,dialout,input,usb nut || true && \
    # Create necessary directories with explicit permissions
    mkdir -p /etc/nut /etc/mail /var/run/nut /run /var/log/nut /usr/share/nut/templates /tmp /app /usr/lib/nut /usr/include /usr/lib/pkgconfig /app/ssl && \
    touch /var/log/msmtp.log /var/log/battery-monitor.log /var/log/nut-debug.log && \
    # Set proper ownership and permissions (explicit for each directory)
    chown -R nut:nut /etc/nut /etc/mail /var/run/nut /run /var/log/nut /var/log /usr/share/nut/templates /tmp /usr/lib/nut /app/ssl && \
    chmod -R 750 /etc/nut /etc/mail /var/run/nut /run && \
    chmod -R 755 /var/log/nut && \
    chmod 777 /tmp && \
    chmod 666 /var/log/msmtp.log /var/log/battery-monitor.log /var/log/nut-debug.log && \
    # Create symbolic link for PID directories to ensure consistent paths
    ln -sf /var/run/nut /run/nut && \
    # Clean apt cache
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy NUT binaries and libraries from builder
COPY --from=builder /tmp/install/usr/bin/upsc /usr/bin/
COPY --from=builder /tmp/install/usr/bin/upscmd /usr/bin/
COPY --from=builder /tmp/install/usr/bin/upsrw /usr/bin/
COPY --from=builder /tmp/install/usr/bin/nut-scanner /usr/bin/
COPY --from=builder /tmp/install/usr/sbin/upsd /usr/sbin/
COPY --from=builder /tmp/install/usr/sbin/upsmon /usr/sbin/
COPY --from=builder /tmp/install/usr/sbin/upsdrvctl /usr/sbin/
COPY --from=builder /tmp/install/usr/share/nut/ /usr/share/nut/
COPY --from=builder /tmp/install/usr/lib/libupsclient* /usr/lib/
COPY --from=builder /tmp/install/usr/lib/libnutscan* /usr/lib/
COPY --from=builder /tmp/install/usr/lib/libnutclient* /usr/lib/
COPY --from=builder /tmp/install/usr/lib/nut/ /usr/lib/nut/
COPY --from=builder /tmp/install/usr/include/nutclient.h /usr/include/
COPY --from=builder /tmp/install/usr/include/nut-scan.h /usr/include/
COPY --from=builder /tmp/install/usr/include/nut_version.h /usr/include/
COPY --from=builder /tmp/install/usr/include/parseconf.h /usr/include/
COPY --from=builder /tmp/install/usr/include/upsclient.h /usr/include/
COPY --from=builder /tmp/install/usr/lib/pkgconfig/libnutclient.pc /usr/lib/pkgconfig/
COPY --from=builder /tmp/install/usr/lib/pkgconfig/libnutscan.pc /usr/lib/pkgconfig/
COPY --from=builder /tmp/install/usr/lib/pkgconfig/libupsclient.pc /usr/lib/pkgconfig/

# Define environment variables for dummy UPS configuration
ENV USE_DUMMY_UPS=false \
    DUMMY_UPS_NAME=dummy \
    DUMMY_UPS_DRIVER=dummy-ups \
    DUMMY_UPS_PORT=dummy \
    DUMMY_UPS_DESC="Virtual UPS for testing"

# Pre-create PID files with proper ownership
RUN touch /var/run/nut/upsd.pid /var/run/nut/driver.pid /run/upsmon.pid && \
    chown nut:nut /var/run/nut/upsd.pid /var/run/nut/driver.pid /run/upsmon.pid && \
    chmod 644 /var/run/nut/upsd.pid /var/run/nut/driver.pid /run/upsmon.pid

# Copy Python dependencies
COPY --from=python-deps /root/.local /root/.local
# Ensure Python binaries are in PATH
ENV PATH=/root/.local/bin:$PATH

# Copy scripts
COPY src/docker-entrypoint /usr/local/bin/
COPY src/start-services.sh /usr/local/bin/
COPY src/generate-settings.sh /usr/local/bin/
COPY nutify/ /app/nutify/

# Set script permissions and create necessary directories
RUN chmod +x /usr/local/bin/docker-entrypoint && \
    chmod +x /usr/local/bin/start-services.sh && \
    chmod +x /usr/local/bin/generate-settings.sh && \
    # Create SSL directory with proper permissions
    mkdir -p /app/ssl && \
    chown -R nut:nut /app/ssl && \
    chmod 750 /app/ssl && \
    # Set ownership
    chown -R nut:nut /app

# Ensure NUT binaries are in PATH
ENV PATH="/usr/bin:/usr/sbin:/root/.local/bin:${PATH}"

# Define environment variables for service startup control
ENV ENABLE_LOG_STARTUP=N \
    SSL_ENABLED=false

# Set working directory to where NUT runs
WORKDIR /var/run/nut

# Expose ports for NUT and web application
EXPOSE 3493/tcp 5050/tcp 443/tcp

# Clear startup chain: generate-settings.sh -> docker-entrypoint -> start-services.sh
ENTRYPOINT ["/usr/local/bin/generate-settings.sh", "/usr/local/bin/docker-entrypoint", "/usr/local/bin/start-services.sh"]

LABEL maintainer="DartSteven <DartSteven@icloud.com>"
