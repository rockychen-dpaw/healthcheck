#!/usr/bin python
import confy
import os
from status import application as app

confy.read_environment_file()
app.run(reloader=True, host='0.0.0.0', port=os.environ.get('PORT'))
