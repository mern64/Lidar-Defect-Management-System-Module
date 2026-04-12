from app import create_app
from app.extensions import db
from app.models import Defect

app = create_app()
with app.app_context():
    defects = Defect.query.all()
    for d in defects:
        d.auto_calculate_priority()
    db.session.commit()
    print("Fixed priorities for all defects.")
