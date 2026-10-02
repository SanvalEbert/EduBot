create table courses (
	course_id int primary key auto_increment,
    course_name varchar(100)
);

create table course_subjects (
	subject_id int primary key auto_increment,
    subject_name varchar(255)
);

create table offerings (
	offering_id int primary key auto_increment,
    course_id int,
    subject_id int,
    foreign key (course_id) references courses(course_id) on delete cascade on update cascade,
    foreign key (subject_id) references course_subjects(subject_id) on delete cascade on update cascade,
    constraint uc_offering unique(course_id, subject_id)
);

create table competencies (
	competency_id int primary key auto_increment,
    competency_description varchar(255),
    subject_id int,
    foreign key (subject_id) references course_subjects(subject_id) on delete cascade on update cascade
);

create table ovas (
	ova_id int primary key auto_increment,
    ova_name varchar(255),
    link varchar(255),
    num_interactions int,
    subject_id int,
    foreign key (subject_id) references course_subjects(subject_id) on delete cascade on update cascade
);

create table questions (
	question_id int primary key auto_increment,
    statement varchar(255),
    alternatives json not null,
    answer varchar(1),
    ova_id int,
    competency_id int,
    foreign key (ova_id) references ovas(ova_id) on delete cascade on update cascade,
	foreign key (competency_id) references competencies(competency_id) on delete cascade on update cascade
);

create table students (
	student_id int primary key auto_increment,
	ra varchar(10),
    student_password varchar(30),
    student_name varchar(100),
    course_id int,
    is_admin boolean,
    foreign key (course_id) references courses(course_id) on delete cascade on update cascade
);

create table answers (
	answer_id int primary key auto_increment,
    student_id int,
    question_id int,
    foreign key (student_id) references students(student_id) on delete cascade on update cascade,
    foreign key (question_id) references questions(question_id) on delete cascade on update cascade,
    constraint uc_answers unique(student_id, question_id)
);

create table interactions (
	interaction_id int primary key auto_increment,
    interaction_date date,
    interaction_time time,
    student_action text,
    student_id int,
    ova_id int,
    foreign key (student_id) references students(student_id) on delete cascade on update cascade,
    foreign key (ova_id) references ovas(ova_id) on delete cascade on update cascade
);
