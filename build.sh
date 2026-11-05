  #!/bin/sh
  echo "People on your network can join at: http://$(hostname -I | awk '{print $1}'):8000"
  sudo docker compose up --build
