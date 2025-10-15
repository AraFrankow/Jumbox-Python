<<<<<<< Updated upstream
from flask import Flask, render_template
=======
from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3

#from flask_bcrypt import Bcrypt
from flask_bcrypt import Bcrypt

# telefono admin: 12345678
# contraseña admin: Admin1234
# telefono usuario1: 87654321
# contraseña usuario1: Usuario1234
>>>>>>> Stashed changes

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)