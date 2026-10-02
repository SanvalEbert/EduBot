import sys, os

# Bootstrap de SCRIPT (não é o padrão do pacote): executado como
# `python tools/init_test_db.py`, o Python coloca tools/ no sys.path — não o
# Back-End/ — e o pacote `edubot` não resolveria. Este insert garante a raiz
# do pacote no path; rodando como módulo (`python -m tools.init_test_db`) é inócuo.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edubot.data.models.base import db
from edubot.data.models.students import Students
from edubot.data.models.courses import Courses
from edubot.data.models.subjects import Subjects
from edubot.data.models.offerings import Offerings
from edubot.data.models.ovas import OVAs
from edubot.data.models.competencies import Competencies
from edubot.data.models.questions import Questions
from edubot.data.models.answers import Answers
from edubot.data.models.resources import Resources
from edubot.data.models.resource_progress import ResourceProgress
from edubot.data.models.ova_progress import OVAProgress
from edubot.data.models.attempts import Attempts
from edubot.data.models.interventions import Interventions


def all_models():
    """Descobre todo Model declarado em edubot/data/models/.

    Esta lista era escrita à mão e ficava defasada a cada model novo: o seed
    criava 17 tabelas enquanto o pacote já tinha 31, e a API quebrava com
    "no such table: learning_events" na primeira rota que tocasse o que faltava.
    Varrendo o pacote, um model novo passa a ser criado sem editar este arquivo.
    """
    import importlib
    import pkgutil

    from peewee import Model

    from edubot.data.models import base as models_base

    pkg_dir = os.path.dirname(os.path.abspath(models_base.__file__))
    found = []
    for mod_info in pkgutil.iter_modules([pkg_dir]):
        if mod_info.name == "base":
            continue
        module = importlib.import_module("edubot.data.models." + mod_info.name)
        for obj in vars(module).values():
            if (isinstance(obj, type) and issubclass(obj, Model)
                    and obj.__name__ not in ("Model", "BaseModel")):
                found.append(obj)
    # dict.fromkeys: um model reexportado por outro módulo (Students dentro de
    # personalized_ova, p.ex.) apareceria duas vezes; a ordem é preservada.
    return list(dict.fromkeys(found))


def init_db():
    db.connect()
    db.create_tables(all_models(), safe=True)

    # Insert minimal sample data
    c = Courses.create(course_name='Engenharia')
    s = Subjects.create(subject_name='Introdução ao Machine Learning')
    Offerings.create(course_id=c, subject_id=s)
    comp1 = Competencies.create(competency_description='Fundamentos de ML supervisionado', subject_id=s)
    comp2 = Competencies.create(competency_description='Conceitos de treino e teste', subject_id=s)
    ova = OVAs.create(ova_name='Intro ML', link='#', num_interactions=0, subject_id=s)
    student = Students.create(ra='1', student_password='1', student_name='Ana Clara', course_id=c, is_admin=False)
    # Questions and answers (comp1 has a correct answer; comp2 is the weak topic)
    q1 = Questions.create(statement='Q1', alternatives='{"alternatives": ["a1", "a2"]}', answer='a', ova_id=ova, competency_id=comp1)
    q2 = Questions.create(statement='Q2', alternatives='{"alternatives": ["a1", "a2"]}', answer='a', ova_id=ova, competency_id=comp2)
    q3 = Questions.create(statement='Q3', alternatives='{"alternatives": ["a1", "a2"]}', answer='b', ova_id=ova, competency_id=comp2)
    # one correct answer recorded (on comp1)
    Answers.create(student_id=student, question_id=q1)
    # resources — MELHORIA (4.1): URL + media type abstraction;
    # MELHORIA (OVA personalizada): competency_id classifica por assunto
    r_text = Resources.create(ova_id=ova, resource_type='texto', resource_title='Texto introdutório', competency_id=comp1)
    r_video = Resources.create(ova_id=ova, resource_type='video', resource_title='Vídeo explicativo',
                               resource_url='https://www.youtube.com/watch?v=aircAruvnKk', media_type='youtube', competency_id=comp1)
    r_pod = Resources.create(ova_id=ova, resource_type='podcast', resource_title='Podcast: ML na prática',
                             resource_url='https://www.soundhelix.com/examples/audio/SoundHelix-Song-1.mp3',
                             media_type='upload', duration_seconds=372, competency_id=comp2)
    Resources.create(ova_id=ova, resource_type='quiz', resource_title='Quiz: Intro ML')
    Resources.create(ova_id=ova, resource_type='atividade', resource_title='Atividade: treine um modelo')
    # MELHORIA (OVA personalizada): banco de remediação da competência fraca (comp2)
    Resources.create(ova_id=ova, resource_type='video', resource_title='Reforço: treino, validação e teste',
                     resource_url='https://www.youtube.com/watch?v=fSytzGwwBVw', media_type='youtube', competency_id=comp2)
    Resources.create(ova_id=ova, resource_type='texto', resource_title='Reforço (texto): overfitting e split de dados',
                     resource_url='https://scikit-learn.org/stable/modules/cross_validation.html', media_type='link', competency_id=comp2)
    # progress
    OVAProgress.create(student_id=student, ova_id=ova, read_time=300, perc_scrolled=65, completed=False)
    ResourceProgress.create(student_id=student, resource_id=r_video, perc_consumed=40, seconds_consumed=120)
    # attempts: comp2 is the weak topic (two wrong tries), comp1 ok
    Attempts.create(student_id=student, question_id=q1, is_correct=True)
    Attempts.create(student_id=student, question_id=q2, is_correct=False)
    Attempts.create(student_id=student, question_id=q3, is_correct=False)
    # intervention
    Interventions.create(student_id=student, date='2026-05-28', type='recomendacao_recurso', description='Sugestão de revisar o vídeo sobre treino e teste.', result='respondeu')

    db.close()


if __name__ == '__main__':
    init_db()
    print('Test DB initialized')
