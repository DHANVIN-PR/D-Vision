from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from tutor_cluster_by_category import cluster_tutors_by_category
import os
from werkzeug.utils import secure_filename
from sklearn.cluster import KMeans
import pandas as pd

app = Flask(__name__, template_folder="templates", static_folder="static")

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "connect_args": {
        "sslmode": "require"
    }
}

# App configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'supersecretkey')
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'static/uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

CATEGORIES = ["Education", "Music", "Sports", "Dance", "Art"]


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # tutor or student
    bio = db.Column(db.Text, nullable=True)
    profile_picture = db.Column(db.String(200), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    tutor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Float, default=0.0)
    materials = db.Column(db.String(200), nullable=True)

    tutor = db.relationship('User', backref='courses')


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    time_slot = db.Column(db.String(100), nullable=False)

    course = db.relationship('Course', backref='bookings')


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    rating = db.Column(db.Float, nullable=False)
    review_text = db.Column(db.Text, nullable=True)


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        role = request.form['role']
        location = request.form.get('location')
        phone = request.form.get('phone')

        if User.query.filter_by(email=email).first():
            flash("Email already registered!", "danger")
            return redirect(url_for('register'))

        new_user = User(
            name=name,
            email=email,
            password=password,
            role=role,
            location=location,
            phone=phone
        )
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful!", "success")
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))

        flash("Invalid email or password", "danger")

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect(url_for('login'))

    selected_category = request.args.get('category')
    selected_cluster = request.args.get('cluster')

    if session['role'] == 'tutor':
        tutor_courses = Course.query.filter_by(tutor_id=session['user_id']).all()
        return render_template('dashboard_tutor.html', courses=tutor_courses, categories=CATEGORIES)

    courses = Course.query.all() if not selected_category else Course.query.filter_by(category=selected_category).all()

    if courses:
        df = pd.DataFrame([{
            'id': c.id,
            'rating': c.rating,
            'category_code': CATEGORIES.index(c.category) if c.category in CATEGORIES else -1
        } for c in courses])

        if len(df) >= 3:
            kmeans = KMeans(n_clusters=3, random_state=42)
            df['cluster'] = kmeans.fit_predict(df[['rating', 'category_code']])
        else:
            df['cluster'] = 0

        cluster_map = dict(zip(df['id'], df['cluster']))
        for c in courses:
            c.cluster = cluster_map.get(c.id, 0)

        if selected_cluster is not None:
            try:
                selected_cluster = int(selected_cluster)
                courses = [c for c in courses if c.cluster == selected_cluster]
            except ValueError:
                pass

    student_bookings = Booking.query.filter_by(student_id=session['user_id']).all()
    return render_template(
        'dashboard_student.html',
        courses=courses,
        categories=CATEGORIES,
        student_bookings=student_bookings
    )


@app.route('/tutor_clusters_by_category')
def tutor_clusters_by_category():
    tutors = User.query.filter_by(role='tutor').all()
    course_data = [{'tutor_id': c.tutor_id, 'category': c.category} for c in Course.query.all()]

    clusters_map = cluster_tutors_by_category(course_data, CATEGORIES)

    cluster_output = []
    for tutor in tutors:
        cluster_output.append({
            'name': tutor.name,
            'email': tutor.email,
            'cluster': clusters_map.get(tutor.id, 0)
        })

    return render_template('tutor_clusters.html', clusters=cluster_output)


@app.route('/search', methods=['GET'])
def search():
    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect(url_for('login'))

    query = request.args.get('query', '')
    courses = Course.query.filter(Course.title.contains(query)).all()
    student_bookings = Booking.query.filter_by(student_id=session['user_id']).all()

    return render_template(
        'dashboard_student.html',
        courses=courses,
        search_query=query,
        categories=CATEGORIES,
        student_bookings=student_bookings
    )


@app.route('/book_course/<int:course_id>', methods=['POST'])
def book_course(course_id):
    if 'user_id' not in session or session['role'] != 'student':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('dashboard'))

    time_slot = request.form['time_slot']
    if not time_slot:
        flash("Please provide a valid time slot!", "warning")
        return redirect(url_for('dashboard'))

    new_booking = Booking(
        student_id=session['user_id'],
        course_id=course_id,
        time_slot=time_slot
    )
    db.session.add(new_booking)
    db.session.commit()

    flash("Course booked successfully!", "success")
    return redirect(url_for('dashboard'))


@app.route('/post_course', methods=['POST'])
def post_course():
    if 'user_id' not in session or session['role'] != 'tutor':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('dashboard'))

    title = request.form['title']
    description = request.form['description']
    category = request.form['category']
    file = request.files.get('materials')
    filename = None

    if file and file.filename:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    new_course = Course(
        title=title,
        description=description,
        category=category,
        tutor_id=session['user_id'],
        materials=filename
    )
    db.session.add(new_course)
    db.session.commit()

    flash("Course posted successfully!", "success")
    return redirect(url_for('dashboard'))


@app.route('/delete_course/<int:course_id>', methods=['POST'])
def delete_course(course_id):
    if 'user_id' not in session or session['role'] != 'tutor':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('dashboard'))

    course = Course.query.get_or_404(course_id)

    if course.tutor_id == session['user_id']:
        db.session.delete(course)
        db.session.commit()
        flash("Course deleted successfully!", "success")

    return redirect(url_for('dashboard'))


@app.route('/course/<int:course_id>')
def course_details(course_id):
    course = Course.query.get_or_404(course_id)
    reviews = Review.query.filter_by(course_id=course_id).all()
    return render_template('course_details.html', course=course, reviews=reviews)


@app.route('/rate_course/<int:course_id>', methods=['POST'])
def rate_course(course_id):
    if 'user_id' not in session:
        flash("Please login first!", "danger")
        return redirect(url_for('login'))

    rating = request.form.get("rating")
    review_text = request.form.get("review")

    if not rating:
        flash("Rating is required!", "danger")
        return redirect(url_for('course_details', course_id=course_id))

    new_review = Review(
        course_id=course_id,
        rating=float(rating),
        review_text=review_text
    )
    db.session.add(new_review)
    db.session.commit()

    reviews = Review.query.filter_by(course_id=course_id).all()
    avg_rating = sum(review.rating for review in reviews) / len(reviews) if reviews else 0.0

    course = Course.query.get(course_id)
    if course:
        course.rating = avg_rating
        db.session.commit()

    flash("Review submitted successfully!", "success")
    return redirect(url_for('course_details', course_id=course_id))


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for('home'))


@app.route('/tutor_clusters')
def tutor_clusters():
    tutors = User.query.filter_by(role='tutor').all()
    data = []

    for tutor in tutors:
        courses = Course.query.filter_by(tutor_id=tutor.id).all()
        if courses:
            avg_rating = sum(course.rating for course in courses) / len(courses)
            data.append({
                'tutor_id': tutor.id,
                'avg_rating': avg_rating,
                'num_courses': len(courses)
            })

    df = pd.DataFrame(data)

    if df.empty or len(df) < 2:
        flash("Not enough tutor data to perform clustering.", "warning")
        return redirect(url_for('dashboard'))

    kmeans = KMeans(n_clusters=3, random_state=42)
    df['cluster'] = kmeans.fit_predict(df[['avg_rating', 'num_courses']])

    clusters = []
    for _, row in df.iterrows():
        tutor = User.query.get(row['tutor_id'])
        clusters.append({
            'name': tutor.name,
            'email': tutor.email,
            'cluster': int(row['cluster']),
            'avg_rating': round(row['avg_rating'], 2),
            'num_courses': int(row['num_courses'])
        })

    return render_template('tutor_clusters.html', clusters=clusters)


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)