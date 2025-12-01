
class EditingHealthCheckMixin(object):
    async def start_editing_healthcheck(self):
        from healthcheck.healthcheck import healthcheck
        from healthcheck.healthcheckserver import EditingServiceHealthCheckTask
        await healthcheck.editing_healthcheck.continuous_check(self.server,taskcls=EditingServiceHealthCheckTask)
        return [True,"OK"]

    def stop_editing_healthcheck(self):
        from healthcheck.healthcheck import healthcheck
        healthcheck.editing_healthcheck.stop_continuous_check()
        return [True,"OK"]

