# set base image (host OS)
FROM public.ecr.aws/docker/library/python:3.12.1

# set the working directory in the container
WORKDIR /

# copy the dependencies file to the working directory
COPY requirements.txt .

# copy the application files
COPY /bin /bin
COPY /src /src

# install dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# set environment variables
ENV PORT 8080

# expose the port
EXPOSE 8080

# command to run on container start
CMD [ "python", "-m", "bin.blockchain_tracker" ]