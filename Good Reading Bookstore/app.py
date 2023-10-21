from flask import Flask, render_template, request, redirect, url_for
import psycopg2.extensions
from psycopg2 import pool
import psycopg2

show_query = {
    "book"          : "SELECT b.booknumber, b.bookname, b.publicationyear, b.pages, string_agg(c.categoryname, ', ') AS category_names, p.publishername FROM public.book b JOIN public.bookcategorylink bc ON b.booknumber = bc.booknumber JOIN public.bookcategory c ON bc.categoryid = c.categoryid JOIN public.publisher p ON b.publisherid = p.publisherid GROUP BY b.booknumber, b.bookname, b.publicationyear, b.pages, p.publishername;",
    "address"       : "SELECT addressid, addressline, city, province, postalcode, telephone FROM public.address ORDER BY addressid ASC;;",
    "author"        : "SELECT authornumber, authorname, yearborn, yeardied FROM public.author;",
    "bookcategory"  : "SELECT categoryid, categoryname, description FROM public.bookcategory;",
    "bookcategorylink" : "SELECT b.booknumber, b.bookname, string_agg(DISTINCT bc.categoryid::text, ', ') AS category_ids, string_agg(DISTINCT c.categoryname, ', ') AS category_names FROM public.book b LEFT JOIN public.bookcategorylink bc ON bc.booknumber = b.booknumber LEFT JOIN public.bookcategory c ON bc.categoryid = c.categoryid GROUP BY b.booknumber, b.bookname;",
    "bookstock"     : "SELECT bs.booknumber, bs.storeid, b.bookname, s.storename, bs.quantity FROM public.bookstock bs JOIN public.book b ON bs.booknumber = b.booknumber JOIN public.store s ON bs.storeid = s.storeid;",
    "customer"      : "SELECT customernumber, customername, a.addressline, a.city, a.province, a.postalcode, a.telephone FROM public.customer c JOIN public.address a ON c.addressid = a.addressid;",
    "publisher"    : "SELECT publisherid, publishername, p.yearfounded, a.addressline, a.city, a.province, a.postalcode, a.telephone FROM public.publisher p JOIN public.address a ON p.addressid = a.addressid;",
    "sale"          : "SELECT s.booknumber, s.customernumber, s.saletime, b.bookname, c.customername, s.price, s.quantity FROM public.sale s JOIN public.book b ON s.booknumber = b.booknumber JOIN public.customer c ON s.customernumber = c.customernumber;",
    "staff"         : "SELECT staffid, staffname, dateofbirth, a.addressline, a.city, a.province, a.postalcode, a.telephone, email, position, salary FROM public.staff s JOIN public.address a ON s.addressid = a.addressid; ",
    "store"         : "SELECT storeid, storename, a.addressline, a.city, a.province, a.postalcode, a.telephone, openeddate, owner FROM public.store s JOIN public.address a ON s.addressid = a.addressid;",
    "writing"       : "SELECT w.booknumber, w.authornumber, b.bookname, a.authorname FROM public.writing w JOIN public.book b ON w.booknumber = b.booknumber JOIN public.author a ON w.authornumber = a.authornumber;"
}

app = Flask(__name__)

connection_pool = psycopg2.pool.SimpleConnectionPool(
    minconn=1,
    maxconn=1000,
    host="52.146.38.251",
    port="5432",
    user="postgres",
    password="ProjectTBD..",
    database="grbookstore"
)

def create_connection():
    return connection_pool.getconn()

def release_connection(conn):
    connection_pool.putconn(conn)

def test_connection():
    conn = create_connection()
    if conn is not None:
        print("Koneksi berhasil!")
        release_connection(conn)  # Return the connection to the pool
    else:
        print("Koneksi gagal!")

def execute_transaction(query):
    with connection_pool.getconn() as conn:
        conn.autocommit = False  # Disable autocommit
        try:
            with conn.cursor() as cursor:
                cursor.execute(query)
            conn.commit()  # Commit the transaction
            print("Transaksi berhasil!")
        except (Exception, psycopg2.DatabaseError) as error:
            conn.rollback()  # Rollback the transaction on error
            print("Terjadi kesalahan saat menjalankan transaksi:", error)
        finally:
            conn.autocommit = True  # Enable autocommit after the transaction
            release_connection(conn)  # Return the connection to the pool

def get_connection():
    conn = create_connection()
    if conn is None:
        raise Exception("Failed to retrieve a connection from the pool.")
    return conn

@app.route('/')
def landing_page():
    return render_template('landing_page.html')

@app.route('/show-tables')
def show_tables():
    conn = get_connection()
    query = "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
    with connection_pool.getconn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            tables = cursor.fetchall()
            return render_template('table_list.html', tables=tables)

@app.route('/show-table-data/<table_name>')
def show_table_data(table_name):
    query = show_query[table_name]
    with get_connection() as conn:  # Remove the conn parameter
        with conn.cursor() as cursor:
            cursor.execute(query)
            table_data = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]
            table_data = [dict(zip(column_names, row)) for row in table_data]
            error_message = request.args.get('error_message')
            success_message = request.args.get('success_message')
            return render_template('table_data.html', table_name=table_name, table_data=table_data, error_message=error_message, success_message=success_message)

@app.route('/delete-data/<table_name>/<int:row_id>', methods=['POST'])
def delete_data(table_name, row_id):
    conn = get_connection()
    with conn.cursor() as cursor:
        try:
            if table_name == 'address':
                cursor.execute("DELETE FROM public.address WHERE addressid = %s", (row_id,))
                conn.commit()
                return redirect(url_for('show_table_data', table_name=table_name, success_message="Data deleted successfully"))
            elif table_name == 'staff':
                cursor.execute("DELETE FROM public.staff WHERE staffid = %s", (row_id,))
                conn.commit()
                return redirect(url_for('show_table_data', table_name=table_name, success_message="Data deleted successfully"))
            else:
                error_message = "Invalid table name."
                return redirect(url_for('show_table_data', table_name=table_name, error_message=error_message))
        except psycopg2.Error as e:
            # Jika terjadi kesalahan, lakukan rollback pada koneksi
            conn.rollback()
            error_message = "Cannot delete the selected data because it is referenced in other tables."
            release_connection(conn)
            return redirect(url_for('show_table_data', table_name=table_name, error_message=error_message))

@app.route('/edit-data/<table_name>/<row_id>', methods=['GET', 'POST'])
def edit_data(table_name, row_id):
    conn = get_connection()
    if request.method == 'POST':
        # Get the updated data from the form
        addressline = request.form['addressline']
        city = request.form['city']
        province = request.form['province']
        postalcode = request.form['postalcode']
        telephone = request.form['telephone']
        # Construct the UPDATE query
        query = f"UPDATE public.{table_name} SET addressline='{addressline}', city='{city}', province='{province}', postalcode='{postalcode}', telephone='{telephone}' WHERE addressid='{row_id}'"
        # Execute the update query
        execute_transaction(query)
        # Redirect to the table data page after the update
        return redirect(url_for('show_table_data', table_name=table_name))
    else:
        # Retrieve the existing data for the selected row
        query = f"SELECT * FROM public.{table_name} WHERE addressid='{row_id}'"
        with conn.cursor() as cursor:
            cursor.execute(query)
            row_data = cursor.fetchone()
            column_names = [desc[0] for desc in cursor.description]
            row_data = dict(zip(column_names, row_data))

        # Render the edit data template with the row data
        return render_template('edit_data.html', table_name=table_name, row_data=row_data)

@app.route('/add-data/<table_name>')
def add_data(table_name):
    conn = get_connection()
    with conn.cursor() as cursor:
        if table_name == 'book':
            cursor.execute("SELECT categoryid, categoryname FROM public.bookcategory")
            bookcategories = cursor.fetchall()
            cursor.execute("SELECT authornumber, authorname FROM public.author")
            authors = cursor.fetchall()
            cursor.execute("SELECT publisherid, publishername FROM public.publisher")
            publishers = cursor.fetchall()
            cursor.execute("SELECT COALESCE(MAX(booknumber), 0) FROM public.book")
            next_book_number = cursor.fetchone()[0] + 1
            return render_template('add_data.html', table_name=table_name, bookcategories=bookcategories,
                                   authors=authors, publishers=publishers, next_book_number=next_book_number)
        elif table_name == 'address':
            return render_template('add_data.html', table_name=table_name)
        elif table_name == 'author':
            return render_template('add_data.html', table_name=table_name)
        elif table_name == 'bookcategory':
            return render_template('add_data.html', table_name=table_name)
        elif table_name == 'staff':
            cursor.execute("SELECT addressid, addressline FROM public.address")
            addresses = cursor.fetchall()
            cursor.execute("SELECT COALESCE(MAX(staffid), 0) FROM public.staff")
            next_staff_id = cursor.fetchone()[0] + 1
            return render_template('add_data.html', table_name=table_name, addresses=addresses, next_staff_id=next_staff_id)
    return render_template('add_data.html', table_name=table_name)

@app.route('/insert-data/<table_name>', methods=['POST'])
def insert_data(table_name):
    conn = get_connection()
    with conn.cursor() as cursor:
        if table_name == 'book':
            bookname = request.form['bookname']
            publicationyear = request.form['publicationyear']
            pages = request.form['pages']
            publishername = request.form['publishername']
            categoryname = request.form['categoryname']
            authorname = request.form['authorname']
            cursor.execute("SELECT publisherid FROM public.publisher WHERE publishername = %s", (publishername,))
            publisher_id = cursor.fetchone()[0]
            cursor.execute("SELECT COALESCE(MAX(booknumber), 0) FROM public.book")
            book_number = cursor.fetchone()[0] + 1
            cursor.execute("INSERT INTO public.book (booknumber, bookname, publicationyear, pages, publisherid) VALUES (%s, %s, %s, %s, %s)",
                           (book_number, bookname, publicationyear, pages, publisher_id))
            cursor.execute("SELECT categoryid FROM public.bookcategory WHERE categoryname = %s", (categoryname,))
            category_id = cursor.fetchone()[0]
            cursor.execute("INSERT INTO public.bookcategorylink (booknumber, categoryid) VALUES (%s, %s)",
                           (book_number, category_id))
            cursor.execute("SELECT authornumber FROM public.author WHERE authorname = %s", (authorname,))
            author_id = cursor.fetchone()[0]
            cursor.execute("INSERT INTO public.writing (booknumber, authornumber) VALUES (%s, %s)",
                           (book_number, author_id))
            conn.commit()
        elif table_name == 'staff' :
            staffname = request.form['staffname']
            dateofbirth = request.form['dateofbirth']
            addressline = request.form['addressline']
            email = request.form['email']
            position = request.form['position']
            salary = request.form['salary']
            cursor.execute("SELECT COALESCE(MAX(staffid), 0) FROM public.staff")
            staff_id = cursor.fetchone()[0] + 1
            cursor.execute("SELECT addressid FROM public.address WHERE addressline = %s", (addressline,))
            address_id = cursor.fetchone()[0]
            cursor.execute("INSERT INTO public.staff (staffid, staffname, dateofbirth, addressid, email, position, salary) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                           (staff_id, staffname, dateofbirth, address_id, email, position, salary))
            conn.commit()

        elif table_name == 'address':
            addressline = request.form['addressline']
            city = request.form['city']
            province = request.form['province']
            postalcode = request.form['postalcode']
            telephone = request.form['telephone']
            cursor.execute("SELECT COALESCE(MAX(addressid), 0) FROM public.address")
            address_id = cursor.fetchone()[0] + 1
            cursor.execute("INSERT INTO public.address (addressid, addressline, city, province, postalcode, telephone) VALUES (%s, %s, %s, %s, %s, %s)",
                           (address_id, addressline, city, province, postalcode, telephone))
            conn.commit()
        elif table_name == 'author':
            authorname = request.form['authorname']
            yearborn = request.form['yearborn']
            yeardied = request.form['yeardied']
            cursor.execute("SELECT COALESCE(MAX(authornumber), 0) FROM public.author")
            author_number = cursor.fetchone()[0] + 1
            if yeardied == '':
                cursor.execute("INSERT INTO public.author (authornumber, authorname, yearborn) VALUES (%s, %s, %s)",
                       (author_number, authorname, yearborn))
            else:
                cursor.execute("INSERT INTO public.author (authornumber, authorname, yearborn, yeardied) VALUES (%s, %s, %s, %s)",
                       (author_number, authorname, yearborn, yeardied))
            conn.commit()
        elif table_name == 'bookcategory':
            categoryname = request.form['categoryname']
            description = request.form['description']
            cursor.execute("SELECT COALESCE(MAX(categoryid), 0) FROM public.bookcategory")
            category_id = cursor.fetchone()[0] + 1
            cursor.execute("INSERT INTO public.bookcategory (categoryid, categoryname, description) VALUES (%s, %s, %s)",
                           (category_id, categoryname, description))
            conn.commit()
    return redirect(url_for('show_table_data', table_name=table_name))

if __name__ == "__main__":
    app.run(debug=True)