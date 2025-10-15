from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from flask_bcrypt import Bcrypt
#a

# telefono admin: 12345678
# contraseña admin: Admin1234
# telefono usuario1: 87654321
# contraseña usuario1: Usuario1234

app = Flask(__name__)
app.secret_key = 'clave_secreta_super_segura'
bcrypt = Bcrypt(app)
DB_NAME = "jumbox.db"

@app.route('/')
def home():
    return render_template('index.html')

@app.errorhandler(404)
def pagina_no_encontrada(e):
    return render_template('404.html'), 404

@app.errorhandler(405)
def pagina_no_encontrada2(e):
    return render_template('404.html'), 405

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        tel = request.form['tel']
        direccion = request.form['direccion']
        contra = request.form['contra']
        confirmar = request.form['confirmar']

        if contra != confirmar:
            flash('Las contraseñas no coinciden', 'error')
            return render_template('registro.html', nombre=nombre, tel=tel, direccion=direccion)
        
        

        hash_contra = bcrypt.generate_password_hash(contra).decode('utf-8')
        
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cliente (nombre, direccion, telefono, contrasena)
                VALUES (?, ?, ?, ?)
            """, (nombre, direccion, tel, hash_contra))
            conn.commit()
            conn.close()

            flash("Registro exitoso", "success")
            return redirect(url_for('registro'))
        except sqlite3.IntegrityError:
            flash("El telefono ya está registrado", "error")
            return redirect(url_for('registro'))

    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        tel = request.form['tel']
        contra = request.form['contra']
    
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id_cliente, nombre, contrasena, tipo FROM cliente WHERE telefono = ?", (tel,))
        cliente = cursor.fetchone()
        conn.close()

        if cliente:
            if bcrypt.check_password_hash(cliente[2], contra):
                session['id_cliente'] = cliente[0]
                session['nombre'] = cliente[1]
                session['tipo'] = cliente[3]
                flash("Inicio de sesión exitoso", "success")
                return redirect(url_for('home'))
        
        flash("Credenciales incorrectas", "error")
        return render_template('login.html', tel=tel)

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente', 'success')
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)