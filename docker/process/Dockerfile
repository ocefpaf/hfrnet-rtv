FROM redhat/ubi9
LABEL Maintainer="nesdis.ocs.assistt.cm@noaa.gov"
COPY docker/process/t4_utils-1.0.2a24-py3-none-any.whl /home
COPY conda_environment.yml /home/
ENV PATH=/usr/share/assistt/compilers/miniconda3/bin:$PATH
RUN dnf update -y && \
    dnf install -y wget uuid zip diffutils && \
    rpm -ivh https://mirror.stream.centos.org/9-stream/AppStream/x86_64/os/Packages/ksh-1.0.6-3.el9.x86_64.rpm && \
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && \
    curl -OL https://truststore.pki.rds.amazonaws.com/us-east-1/us-east-1-bundle.pem && \
    bash Miniconda3-latest-Linux-x86_64.sh -b -p /usr/share/assistt/compilers/miniconda3 && \
    rm Miniconda3-latest-Linux-x86_64.sh && \
    sed -i -e 's/name: .*/name: base/' -e '/^prefix:/d' /home/conda_environment.yml && \
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main && \
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r && \
    conda env update --file /home/conda_environment.yml && \
    conda clean --all --yes && \
    pip install /home/t4_utils-1.0.2a24-py3-none-any.whl && \
    mkdir /home/WORKING_DIR && \
    cp -rf us-east-1-bundle.pem /home/WORKING_DIR && \
    rm /home/conda_environment.yml && \
    rm /home/t4_utils-1.0.2a24-py3-none-any.whl && \
    rm us-east-1-bundle.pem && \
    chmod 777 /home/WORKING_DIR
WORKDIR /home/WORKING_DIR
USER 1000
# curl -OL https://truststore.pki.rds.amazonaws.com/us-east-1/us-east-1-bundle.pem && \

