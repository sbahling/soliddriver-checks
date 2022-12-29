import click
import json
from ..api import analysis
from ..api.km import read_remote_json
from .terminal_logs import KMPTerminalOutput, single_kmp_output
from .kmp_report import KMPReporter
from .km_report import KMReporter
import os
import logging
import socket
from pathlib import Path
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from ..version import __VERSION__
from urllib.parse import urlparse


FORMAT_TYPES = {
    "html": ".html",
    "xlsx": ".xlsx",
    "json": ".json",
}


class Check_Target:
    def __init__(self, target):
        if target is None:
            target = "system"

        self._target = target

    @property
    def system(self):
        target = Path(self._target)
        return target.name == "system" and not (
            target.is_file() or target.is_dir()
        )

    @property
    def rpm(self):
        # need better check than this
        target = Path(self._target)
        if target.is_file() and target.name.endswith(".rpm"):
            return target
        return None

    @property
    def dir(self):
        target = Path(self._target)
        if target.is_dir():
            return target
        return None

    @property
    def url(self):
        try:
            self._url = urlparse(self._target)
            if all([self._url.scheme, self._url.netloc]):
                return self._target

            return None
        except:
            return None

    @property
    def url_host(self):
        if self.url is not None:
            return self._url.hostname
        return None


def with_format_suffix(path, format_type):
    suffix = FORMAT_TYPES.get(format_type, None)

    if suffix is None:
        return path

    if path.suffix == suffix:
        return path

    return path.parent / (path.name + suffix)


def kmp_export(exporter, check_result, out_format, dst):
    dst = with_format_suffix(dst, out_format)
    if out_format == "html":
        exporter.to_html(check_result, dst)
    elif out_format == "xlsx":
        exporter.to_xlsx(check_result, dst)
    elif out_format == "json":
        exporter.to_json(check_result, dst)


def km_export(exporter, label, check_result, out_format, dst):
    dst = with_format_suffix(dst, out_format)
    if out_format == "html":
        exporter.to_html(label, check_result, dst)
    elif out_format == "xlsx":
        exporter.to_xlsx(label, check_result, dst)
    elif out_format == "json":
        exporter.to_json(label, check_result, dst)


def dst_is_ok(dst, out_format):
    def check(dst):
        if dst.is_file():
            if not os.access(dst, os.W_OK):
                raise Exception("Cannot write to %s" % dst)
            return click.confirm("Overwrite %s?" % dst)
        return True

    if out_format == "all":
        for format_type, ext in FORMAT_TYPES.items():
            if ext is None:
                continue
            dst = dst.parent / (dst.name + ext)
            if not check(dst):
                return False
        return True

    else:
        ext = FORMAT_TYPES[out_format]
        dst = dst.parent / (dst.name + ext)
        return check(dst)


@click.command()
@click.argument("check_target", default="system")
@click.option(
    "--format",
    "-f",
    "out_format",
    type=click.Choice(FORMAT_TYPES),
    default="json",
    help="Specify output format (PDF is in Beta)",
)
@click.option(
    "--output",
    "-o",
    default=".",
    help="Output destination. Target can be filename or point "
    "existing directory "
    "If directory, files will be placed in the directory "
    "using a autmatically generated filename. If target "
    "is not an existing directory, file name is assumed "
    "and output files will use the path and file name "
    "specified. In either case, the file extension will "
    "be automatically appended matching on the output format",
)
@click.option("--version", is_flag=True)
def run(check_target, output, out_format, version):
    """Run checks against CHECK_TARGET.

    \b
    CHECK_TARGET can be:
      KMP file
      directory containing KMP files
      "system" to check locally installed kernel modules
    """

    if version:
        print(__VERSION__)
        exit()

    FORMAT = "%(asctime)-15s %(message)s"
    logging.basicConfig(format=FORMAT, handlers=[RichHandler()])
    logger = logging.getLogger("rich")
    logger.setLevel(logging.INFO)

    target = Check_Target(check_target)

    dst = Path(output)
    if dst.is_dir() or output.endswith("/"):
        dst = dst / "check_result"

    if not dst_is_ok(dst, out_format):
        logger.error("Can't write to output")
        exit(1)

    # try to guess format from file extension
    if out_format is None:
        ext_to_format = {v: k for k, v in FORMAT_TYPES.items()}
        out_format = ext_to_format.get(dst.suffix, None)

    if target.rpm:
        df = analysis.kmp_analysis(target.rpm)
        single_kmp_output(df)

    elif target.dir:
        progress = Progress(
            "{task.description}",
            SpinnerColumn(),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        )
        with progress:
            log = KMPTerminalOutput(progress)
            df = analysis.kmps_to_dataframe(target.dir, log)
        reporter = KMPReporter()
        kmp_export(reporter, df, out_format, dst)
        logger.info(
            "[green]Check is completed![/]"
            "The result has been saved to "
            "[bold green]%s[/]" % dst,
            extra={"markup": True},
        )

    elif target.system:
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
        except socket.gaierror as e:
            logger.warning(f"Get ip by hostname: {hostname} failed: {e}")
            ip = "127.0.0.1"

        label = "%s (%s)" % (hostname, ip)
        logger.info("Retrieving kernel module data for %s" % label)
        reporter = KMReporter()
        km_export(reporter, label, None, out_format, dst)
    elif target.url:
        df = read_remote_json(target.url)
        reporter = KMReporter()
        km_export(reporter, target.url_host, df, out_format, dst)

if __name__ == "__main__":
    run()
