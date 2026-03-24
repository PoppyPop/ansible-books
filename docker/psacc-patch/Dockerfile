FROM flobz/psa_car_controller:v3

# Copy the patch
COPY trip.patch /tmp/trip.patch

# install patch utility
RUN apt-get update && apt-get install -y patch

# Apply the patch
RUN cd / && patch -p1 < /tmp/trip.patch
