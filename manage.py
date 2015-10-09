import os
from status import application as app

app.run(reloader=True,port=os.environ.get('PORT'))
