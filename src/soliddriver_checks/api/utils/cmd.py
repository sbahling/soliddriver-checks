import subprocess


def get_max_args():
    return int(run_cmd("getconf ARG_MAX"))

def async_run_cmd(
    cmd, line_handler, line_handler_arg, start, end, condition, sshClient=None
):
    if sshClient is not None:
        __, stdout, __ = sshClient.exec_command(cmd)

        lines = stdout.read().decode().splitlines()
        for line in lines:
            line_handler(line_handler_arg, line.strip(), start, condition)
            start += 1
            if start >= end:
                break

        # channel = sshClient.get_transport().open_session()
        # channel.exec_command(cmd)

        # while not channel.exit_status_ready():
        #     r, __, __ = select.select([channel], [], [])
        #     if len(r) > 0:
        #         recv = channel.recv(1024)
        #         recv = str(recv, "utf-8").splitlines()
        #         for line in recv:
        #             line_handler(line_handler_arg, line, start, condition)
        #             start += 1

        # channel.close()
    else:
        cmd_runner = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        for line in cmd_runner.stdout:
            line = str(line, "utf-8")
            line_handler(line_handler_arg, line, start, condition)
            start += 1
            if start >= end:
                break


def run_cmd(cmd, sshClient=None, timeout=None):
    if sshClient is not None:
        __, stdout, __ = sshClient.exec_command(cmd, timeout=timeout)
        result = stdout.read()
        return str(result, "utf-8")
    else:
        cmd_runner = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        result, __ = cmd_runner.communicate()
        return str(result, "utf-8")
    