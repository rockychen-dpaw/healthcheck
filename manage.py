import os
from status import application as app

app.run(reloader=True,host='0.0.0.0',port=os.environ.get('PORT'))
