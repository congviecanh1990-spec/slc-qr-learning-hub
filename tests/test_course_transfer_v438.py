"""Offline SQLite regression test for handover: exact production models + SQL predicate.

Uses a minimal Flask-SQLAlchemy interface shim when Flask deps aren't installed.
Does not simulate authentication, OAuth, or live Render/PostgreSQL.
"""
from __future__ import annotations
import ast
from pathlib import Path
import sys, types
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, relationship, backref, sessionmaker

ROOT=Path(__file__).resolve().parents[1]
try:
    import flask_sqlalchemy  # noqa: F401
    from flask_sqlalchemy import SQLAlchemy
except ModuleNotFoundError:
    class SQLAlchemy:
        def __init__(self):
            self.Model = declarative_base()
            for key in ('Column', 'Integer', 'String', 'Text', 'Date', 'DateTime', 'Boolean',
                        'Float', 'ForeignKey'):
                setattr(self, key, getattr(sa, key))
            self.relationship=relationship
            self.backref=backref
    module=types.ModuleType('flask_sqlalchemy');module.SQLAlchemy=SQLAlchemy
    sys.modules['flask_sqlalchemy']=module
sys.path.insert(0,str(ROOT))
import models

engine=sa.create_engine('sqlite:///:memory:')
models.db.Model.metadata.create_all(engine)
Session=sessionmaker(bind=engine)
with Session() as session:
    models.db.session=session
    a=models.User(email='a@example.test',name='GV A',role='lecturer',lecturer_code='GV0001')
    b=models.User(email='b@example.test',name='GV B',role='lecturer',lecturer_code='GV0002')
    admin=models.User(email='admin@example.test',name='Quản trị',role='admin',lecturer_code='GV0003')
    session.add_all([a,b,admin]);session.flush()
    course=models.Course(owner_id=a.id,code='HP000001',name='Lập trình',active=True)
    session.add(course);session.flush()
    original=models.QrCode(owner_id=a.id,course_id=course.id,slug='unchanged-slug',title='Video hướng dẫn',active=True)
    free=models.QrCode(owner_id=a.id,course_id=None,slug='free-a',title='QR riêng A',active=True)
    session.add_all([original,free]);session.commit()

    # Execute precisely the two access-control functions from the application source.
    mod=ast.parse((ROOT/'app.py').read_text())
    names={'managed_qr_scope','qr_managed_by_user'}
    funcs=[n for n in mod.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert len(funcs)==2
    env={'db':models.db,'Course':models.Course,'QrCode':models.QrCode,'and_':sa.and_,'or_':sa.or_,'User':models.User}
    exec(compile(ast.Module(body=funcs,type_ignores=[]),'<app QR ACL>','exec'),env)
    visible=lambda uid: set(x.slug for x in session.query(models.QrCode).filter(env['managed_qr_scope'](uid)).all())
    assert visible(a.id)=={'unchanged-slug','free-a'}
    assert visible(b.id)==set()
    # Transfer changes ONLY course owner. The printed QR and original authorship are unchanged.
    previous=course.owner_id
    course.owner_id=b.id
    session.add(models.CourseTransfer(course_id=course.id,previous_owner_id=previous,new_owner_id=b.id,
                                      changed_by=admin.id,effective_on=models.utcnow().date()))
    session.commit()
    assert original.slug=='unchanged-slug' and original.owner_id==a.id
    assert visible(a.id)=={'free-a'},visible(a.id)
    assert visible(b.id)=={'unchanged-slug'},visible(b.id)
    assert env['qr_managed_by_user'](original,b) is True
    assert env['qr_managed_by_user'](original,a) is False
    assert session.query(models.CourseTransfer).count()==1
    assert session.query(models.CourseTransfer).first().previous_owner_id==a.id
    # For repeated transfers, latest course owner controls, not historical author.
    course.owner_id=admin.id
    session.add(models.CourseTransfer(course_id=course.id,previous_owner_id=b.id,new_owner_id=admin.id,
                                      changed_by=admin.id,effective_on=models.utcnow().date()))
    session.commit()
    assert visible(b.id)==set() and visible(admin.id)=={'unchanged-slug'}
    assert original.slug=='unchanged-slug' and original.owner_id==a.id
print('PASS: real models + SQLite: handover, original QR, scoped access, unassigned QR, retransfer history')
