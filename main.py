import sqlite3
import sys
from PyQt6 import uic
from PyQt6.QtWidgets import QMainWindow, QApplication, QDialog, QFrame, QWidget, QVBoxLayout, QLineEdit
from PyQt6.QtCore import QDate
import school_mos
from winotify import Notification
from apscheduler.schedulers.background import BackgroundScheduler
import datetime




class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        uic.loadUi('QT_pages/main_window.ui', self)
        self.login_btn.clicked.connect(login_btn_f)
        self.exit_btn.clicked.connect(exit_btn_f)
        self.filter_btn.clicked.connect(lambda: api_homework_magic(subject=self.filter_input.text()))
        self.date_chooser1.clicked.connect(api_homework_magic)
        self.show()


class LoginWindow(QDialog):
    def __init__(self):
        super(LoginWindow, self).__init__()
        uic.loadUi('QT_pages/password_input.ui', self)
        self.enter_btn.clicked.connect(password_processing)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.show()


class Pattern(QFrame):
    def __init__(self):
        super(Pattern, self).__init__()
        uic.loadUi('QT_pages/homework_pattern.ui', self)
        self.ADD_btn.clicked.connect(self.add_date)
        self.notification_checkbox.toggled.connect(self.collapse)
        self.REMOVE_btn.clicked.connect(self.remove_date)
        self.dates = []
        self.collapse()

    def add_date(self):
        global user
        subject, desc, calendar, toggle, time = self.get_info()
        calendar_time = calendar.toString('dd-MM-yyyy') + ' ' + time
        if calendar_time not in self.dates:
            self.dates.append(calendar_time)
            self.status_label.setText('')
            self.Datas_label.setText('\n'.join(self.dates))
            connection = sqlite3.connect('data/app_homework.db')
            cursor = connection.cursor()
            token = user.token[:15]
            data = cursor.execute(f"""
                SELECT homework_id FROM homeworks WHERE description = '{self.homework_label.text()}' AND student_id = (SELECT student_id FROM students WHERE part_of_token = '{token}')
                AND subject_id = (SELECT subject_id FROM subjects WHERE subject_name = '{self.homework_subject_label.text()}');
                """).fetchall()
            cursor.execute(f"""
                INSERT INTO notify_times (notify_time, homework_id) VALUES ('{calendar_time}', '{data[0][0]}');
                """)
            connection.commit()
            connection.close()
        else:
            self.status_label.setText('Ошибка добавления: объект уже существует')

    def remove_date(self):
        subject, desc, calendar, toggle, time = self.get_info()
        calendar_time: object = calendar.toString('dd-MM-yyyy') + ' ' + time
        if calendar_time in self.dates:
            self.dates.remove(calendar_time)
            db_remove(self, calendar_time)
            self.status_label.setText('')
            self.Datas_label.setText('\n'.join(self.dates))
        else:
            self.status_label.setText('Ошибка удаления: нет объекта')

    def get_info(self):
        calendar = self.calendar.selectedDate()
        desc = self.homework_label.text()
        subject = self.homework_subject_label.text()
        toggle = self.notification_checkbox.isChecked()
        time = self.Time_hour_minutes.text()
        return subject, desc, calendar, toggle, time

    def collapse(self):
        subject, desc, calendar, toggle, time = self.get_info()
        if toggle:
            add_to_db(self)
            self.resize(868, 338)
        else:
            self.resize(310, 338)


class Wid(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)


def login_btn_f():
    login_win.show()


def db_check(task):
    global user
    token = user.token[:15]
    connection = sqlite3.connect('data/app_homework.db')
    cursor = connection.cursor()
    data = cursor.execute(f"""
    SELECT homework_id, notify_about FROM homeworks WHERE description = '{task.description}' AND student_id = (SELECT student_id FROM students WHERE part_of_token = '{token}')
    AND subject_id = (SELECT subject_id FROM subjects WHERE subject_name = '{task.subject_name}');
    """).fetchall()
    switch = True
    if len(data) == 0:
        switch = False
    else:
        if not data[0][1]:
            switch = False
        data = data[0][0]

    dates = cursor.execute(f"""SELECT notify_time FROM notify_times WHERE homework_id = '{data}';""").fetchall()
    connection.commit()
    connection.close()
    new_task = [task.description, task.subject_name, switch, dates]
    return new_task


def db_remove(pattern, time):
    connection = sqlite3.connect('data/app_homework.db')
    cursor = connection.cursor()
    subject_name = pattern.homework_subject_label.text()
    description = pattern.homework_label.text()
    part_of_token = user.token[:15]
    subject_id = cursor.execute(f"""
    SELECT subject_id FROM subjects WHERE subject_name = '{subject_name}'
    """).fetchall()[0][0]
    student_id = cursor.execute(f"""
    SELECT student_id FROM students WHERE part_of_token = '{part_of_token}'
    """).fetchall()[0][0]
    data = cursor.execute(f"""
    SELECT homework_id FROM homeworks WHERE description = '{description}' AND student_id = '{student_id}'
    AND subject_id = '{subject_id}';""").fetchall()[0][0]
    cursor.execute(f"""DELETE FROM notify_times WHERE homework_id = {data} AND notify_time = '{time}'""")
    eventScheduler_from_db()
    connection.commit()
    connection.close()


def add_to_db(pattern):
    global user
    """
    берет паттерн и пихает его в базу данных если его там еще нет
    """
    connection = sqlite3.connect('data/app_homework.db')
    cursor = connection.cursor()

    description = pattern.homework_label.text()
    notify = pattern.notification_checkbox.isChecked()
    part_of_token = user.token[:15]
    subject_name = pattern.homework_subject_label.text()
    if len(cursor.execute(f"""
    SELECT * FROM subjects WHERE subject_name = '{subject_name}';
    """).fetchall()) == 0:
        cursor.execute(f"""
        INSERT INTO subjects (subject_name)
             VALUES ('{subject_name}');
        """)
    subject_id = cursor.execute(f"""
    SELECT subject_id FROM subjects WHERE subject_name = '{subject_name}'
    """).fetchall()[0]

    if len(cursor.execute(f"""
    SELECT * FROM students WHERE part_of_token = '{part_of_token}'
    """).fetchall()) == 0:
        cursor.execute(f"""
        INSERT INTO students (part_of_token) VALUES ('{part_of_token}');
        """)
    student_id = cursor.execute(f"""
    SELECT student_id FROM students WHERE part_of_token = '{part_of_token}'
    """).fetchall()[0]

    subject_id = subject_id[0]
    student_id = student_id[0]
    data = cursor.execute(f"""
    SELECT homework_id, notify_about FROM homeworks WHERE description = '{description}' AND student_id = '{student_id}'
    AND subject_id = '{subject_id}';
    """).fetchall()
    if len(data) == 0:
        cursor.execute(f"""
        INSERT INTO homeworks (description, student_id, subject_id, notify_about) VALUES ('{description}', '{student_id}', '{subject_id}', '{int(notify)}');
        """)
    connection.commit()
    connection.close()
    eventScheduler_from_db()


def exit_btn_f():
    main_win.exit_btn.setEnabled(False)
    main_win.filter_label.setEnabled(False)
    main_win.login_btn.setEnabled(True)
    main_win.filter_input.setEnabled(False)
    main_win.filter_btn.setEnabled(False)
    main_win.loginLabel.setText('Вы не вошли')
    for i in reversed(range(scrollarea_widget.layout.count())):
        scrollarea_widget.layout.itemAt(i).widget().setParent(None)


def api_login_magic(login, password):
    global user
    try:
        user = school_mos.AUTH(_login=login, _password=password, show_token=True)
    except Exception:
        return True
    return user


def create_notification(title, desc):
    toast = Notification(app_id='HomeworkApp',
                         title=title,
                         msg=desc,
                         duration='long')
    toast.show()


def api_homework_magic(subject=''):
    global user, main_win, scrollarea_widget
    for i in reversed(range(scrollarea_widget.layout.count())):
        scrollarea_widget.layout.itemAt(i).widget().setParent(None)
    chosen_date = main_win.daychooser.selectedDate()
    main_win.label.setText(chosen_date.toString('dd-MM-yyyy'))
    date_range = QDate.currentDate().daysTo(chosen_date)
    try:
        daily_homework = user.homework.get_by_date(date_offset=date_range)
        for task in daily_homework:
            if subject == '' or task.subject_name.lower() == subject.lower():
                task = db_check(task)
                make_homework_pattern(task[0], task[1], task[2], task[3])

    except Exception:
        return


def make_homework_pattern(description='', subject='', checked=False, dates=None):
    if dates is None:
        dates = []
    global scrollarea_widget
    newpattern = Pattern()
    newpattern.homework_label.setText(description)
    for i in range(len(dates)):
        dates[i] = dates[i][0]
    newpattern.dates = dates
    newpattern.Datas_label.setText('\n'.join(dates))
    newpattern.homework_subject_label.setText(subject)
    newpattern.notification_checkbox.setChecked(checked)
    scrollarea_widget.layout.addWidget(newpattern)
    newpattern.notification_checkbox.click()
    newpattern.notification_checkbox.click()


def password_processing():
    global user
    login = login_win.login_input.text()
    password = login_win.password_input.text()
    user = api_login_magic(login, password)
    if type(user) is bool:
        login_win.warning_label.setText('Ошибка API')
        return

    api_homework_magic()
    main_win.exit_btn.setEnabled(True)
    main_win.loginLabel.setText('Вы вошли как\n' + user.first_name)
    login_win.warning_label.setText('(не сохраняются после завершения сессии)')
    main_win.filter_label.setEnabled(True)
    main_win.login_btn.setEnabled(False)
    main_win.filter_input.setEnabled(True)
    main_win.filter_btn.setEnabled(True)
    main_win.daychooser.setEnabled(True)
    login_win.login_input.clear()
    login_win.password_input.clear()
    login_win.hide()

def eventScheduler_from_db():
    bs = BackgroundScheduler()
    connection = sqlite3.connect('data/app_homework.db')
    cursor = connection.cursor()
    bs.remove_all_jobs()
    results = cursor.execute(f"""
    SELECT * FROM notify_times;
    """).fetchall()
    for position in results:
        desc, subj_id, notify_abt = cursor.execute(f"""SELECT description, subject_id, notify_about FROM homeworks WHERE homework_id = '{position[0]}'""").fetchall()[0]
        subj = cursor.execute(F"""SELECT subject_name FROM subjects WHERE subject_id = '{subj_id}'""").fetchall()[0][0]
        scheduler_handler(position, notify_abt, subj, desc, bs)
    for job in bs.get_jobs():
        print(job.id)
    print('-----', datetime.datetime.now())
    bs.start()



def scheduler_handler(position, notify_abt, subj, desc, bs):
    date_time_obj = datetime.datetime.strptime(position[1], '%d-%m-%Y %H:%M')
    flag = True
    for job in bs.get_jobs():
        if job.id == str(position[0]).rjust(10, '0') + str(date_time_obj):
            flag = False
    if flag and notify_abt:
        bs.add_job(create_notification, run_date=date_time_obj, args=[subj, desc], id=(str(position[0]).rjust(10, '0') + str(date_time_obj)))


if __name__ == '__main__':
    eventScheduler_from_db()
    app = QApplication(sys.argv)
    main_win = MainWindow()
    login_win = LoginWindow()
    scrollarea_widget = Wid()
    main_win.scroll_area.setWidget(scrollarea_widget)
    login_win.hide()
    sys.exit(app.exec())
