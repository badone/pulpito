from pecan import conf, expose, redirect, request
import requests

from job import JobController
from util import get_job_status_class, get_job_time_info
from pulpito.controllers import error
from pulpito.controllers.errors import ErrorsController
from pulpito.controllers.compare import RunCompareController
from pulpito.controllers.util import get_run_filters

base_url = conf.paddles_address


class RootController(object):

    errors = ErrorsController()

    @expose('index.html')
    def index(self, latest=False, branch='', machine_type='', status='',
              suite='', date='', to_date=''):
        filters = get_run_filters(latest=latest, branch=branch,
                                  machine_type=machine_type, status=status,
                                  suite=suite, date=date, to_date=to_date)
        request.context['filters'] = filters

        uri = '{base}/runs/'.format(base=base_url)
        if branch:
            uri += 'branch/%s/' % branch
        if machine_type:
            uri += 'machine_type/%s/' % machine_type
        if status:
            uri += 'status/%s/' % status
        if suite:
            uri += 'suite/%s/' % suite
        if to_date and date:
            uri += 'date/from/{from_}/to/{to}/'.format(from_=date, to=to_date)
        elif date:
            uri += 'date/%s/' % date
        if status == 'running':
            uri += '?count=9999'

        latest_runs = requests.get(uri).json()
        for run in latest_runs:
            run['posted'] = run['posted'].split('.')[0]
            run['status_class'] = self.set_status_class(run)
        return dict(runs=latest_runs,
                    filters=request.context.get('filters', dict()),
                    branch=branch,
                    machine_type=machine_type,
                    suite=suite,
                    dates=[date, to_date],
                    )

    @expose('index.html')
    def latest(self, **kwargs):
        return self.index(latest=True, **kwargs)

    def set_status_class(self, run):
        fail = run['results']['fail']
        running = run['results']['running']
        passing = run['results']['pass']
        status_class = 'warning'
        if fail:
            status_class = 'danger'
        elif not running and passing:
            status_class = 'success'
        elif running and passing:
            status_class = 'warning'
        else:
            status_class = 'warning'
        return status_class

    @expose('index.html')
    def date(self, from_date_str, to='', to_date_str=''):
        filters = get_run_filters(date=from_date_str, to_date=to_date_str)
        request.context['filters'] = filters
        if to:
            resp = requests.get(
                '{base}/runs/date/from/{from_}/to/{to}'.format(
                    base=base_url, from_=from_date_str, to=to_date_str))
        else:
            resp = requests.get('{base}/runs/date/{date}/'.format(
                base=base_url, date=from_date_str))

        if resp.status_code == 400:
            error('/errors/invalid/',
                  resp.json().get('message'))
        elif resp.status_code == 404:
            error('/errors/not_found/',
                  resp.json().get('message'))
        else:
            runs = resp.json()

        for run in runs:
            run['status_class'] = self.set_status_class(run)
        return dict(runs=runs,
                    filters=request.context.get('filters', dict()),
                    dates=[from_date_str, to_date_str]
                    )

    compare = RunCompareController()

    @expose()
    def _lookup(self, name, *remainder):
        return RunController(name), remainder


class RunController(object):

    def __init__(self, name):
        self.name = name
        self.run = None

    def get_run(self):
        resp = requests.get(
            '{base}/runs/{name}'.format(base=base_url,
                                        name=self.name))
        if resp.status_code == 404:
            error('/errors/not_found/',
                  'requested run does not exist')
        else:
            run = resp.json()

        if 'scheduled' in run:
            run['scheduled_day'] = run['scheduled'].split()[0]

        if 'jobs' in run:
            for job in run['jobs']:
                job['posted_pretty'] = job['posted'].split('.')[0]
                job['updated_pretty'] = job['updated'].split('.')[0]
                job['status_class'] = get_job_status_class(job)
                job['duration_pretty'] = get_job_time_info(job)

        self.run = run
        return self.run

    @expose('run.html')
    def index(self):
        run = self.run or self.get_run()
        return dict(
            run=run
        )

    @expose('json')
    def _lookup(self, job_id, *remainder):
        return JobController(self.name, job_id), remainder
