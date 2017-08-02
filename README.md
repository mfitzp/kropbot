# Remote Control Robot

## Requirements

- Flask
- SQLAlchemy
- flask-sqlalchemy
- psycopg2
- gunicorn
- flask-socketio
- eventlet

## Implementation

- Flask (+Postgres) backend with AngularJs (+Bootstrap) frontend
- Communication between the backend and admin page is via websockets (Socket.IO) giving real time updates
- Simple tests are implemented in `test.py` which validate expected behaviours.

## Run locally

The socket implementation can be run with `gunicorn` or directly. To run from the command line use:

    python app.py

Or:

    gunicorn --worker-class eventlet -w 1 app:app

## Heroku

A Procfile is included to run the app on a Heroku instance.


To set up your own named instance use:

    heroku login
    heroku git:remote -a [instance]   # Add the heroku remote
    git push heroku master        # Push up the current code
    heroku ps:scale web=1

To set up the database add a Postgres database (Hobby Dev level) to your instance using the Heroku interface.
This should automatically add the `DATABASE_URL` setting to your config variables (see Settings -> Config Variables)
if unsure. The database URL should be in `postgres://` format.

To create initial database tables run Python on the Heroku instance.

    heroku run python

Then in the interpreter create database tables as follows:

    from app import db
    db.create_all()

Access your instance at http://[instance].herokuapp.com


