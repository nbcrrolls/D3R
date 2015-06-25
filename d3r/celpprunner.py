#! /usr/bin/env python

import sys
import errno
import os
import argparse
import psutil
import logging

import d3r.task
from d3r.task import D3RParameters
from d3r.task import BlastNFilterTask
from lockfile.pidlockfile import PIDLockFile

# create logger
logger = logging.getLogger('d3r.celpprunner')
LOG_FORMAT = "%(asctime)-15s %(levelname)s %(name)s %(message)s"


def _get_lock(theargs):
    """Create lock file to prevent this process from running on same data

       This uses ``PIDLockFile`` to create a pid lock file in celppdir
       directory named celprunner.<stage>.lockpid
       If pid exists it is assumed the lock is held otherwise lock
       is broken and recreated

       :param theargs: return value from argparse and should contain
                       theargs.stage which denotes stage of processing
                       and theargs.celppdir should be set to path
       :return: ``PIDLockFile`` upon success
       :raises: LockException
       """
    mylockfile = os.path.join(theargs.celppdir, "celpprunner." +
                              theargs.stage + ".lockpid")
    logger.debug("Looking for lock file: " + mylockfile)
    lock = PIDLockFile(mylockfile, timeout=10)

    if lock.i_am_locking():
        logger.debug("My process id" + str(lock.read_pid()) +
                     " had the lock so I am breaking")
        lock.break_lock()
        lock.acquire(timeout=10)
        return lock

    if lock.is_locked():
        logger.debug("Lock file exists checking pid")
        if psutil.pid_exists(lock.read_pid()):
            raise Exception("celpprunner with pid " +
                            str(lock.read_pid()) +
                            " is running")

    lock.break_lock()
    logger.info("Acquiring lock")
    lock.acquire(timeout=10)
    return lock


def _setup_logging(theargs):
    """Sets up the logging for application
       """
    theargs.logFormat = LOG_FORMAT
    logger.setLevel(theargs.logLevel)
    logging.basicConfig(format=theargs.logFormat)
    logging.getLogger('d3r.task').setLevel(theargs.logLevel)

def run_stage(theargs):
    latestWeekly = d3r.task.find_latest_weekly_dataset(theargs.celppdir)

    if latestWeekly is None:
        logger.info("No weekly dataset found in path " +
                    theargs.celppdir)
        return 0

    logger.info("Starting " + theargs.stage + " stage")

    # perform processing
    if theargs.stage == 'blast':
        task = BlastNFilterTask(latestWeekly,theargs)

    if theargs.stage == 'dock':
        raise NotImplementedError('uh oh dock is not implemented yet')

    if theargs.stage == 'score':
        raise NotImplementedError('uh oh score is not implemented yet')

    if task.can_run():
        logger.info("Running task " + task.get_name())
        task.run()
        logger.debug("Task " + task.get_name() + " has finished running " +
                     " with status " + task.get_status())
    if task.get_error() != None:
        logger.error('Error running task ' + task.get_name() +
                     ' ' + task.get_error())
        return 1
    return 0

def _parse_arguments(desc, args):
    """Parses command line arguments
       """
    parsed_arguments = D3RParameters()

    helpFormatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(description=desc,
                                     formatter_class=helpFormatter)
    parser.add_argument("celppdir", help='Base celpp directory')
    parser.add_argument("--blastdir", help='Parent directory of ' +
                        ' blastdb.  There should exist a "current" ' +
                        ' symlink or folder that contains the db.')
    parser.add_argument("--email",
                        help='Comma delimited list of email addresses')

    parser.add_argument("--stage", choices=['blast', 'dock', 'score'],
                        required=True, help='Stage to run blast = ' +
                        'blastnfilter (2), dock = fred & other ' +
                        'docking algorithms (3), ' +
                        'score = scoring (4)')
    parser.add_argument("--log", dest="logLevel", choices=['DEBUG',
                        'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help="Set the logging level",
                        default='WARNING')

    return parser.parse_args(args, namespace=parsed_arguments)


def main():

    desc = """
              Runs last 3 stages of CELPP processing pipeline (blast,
              dock, and score).

              CELPP processing pipeline is basically a set of folders
              with specific structure.  The pipeline runs a set of
              what are known as stages.  Each stage has a numerical
              value and a name.  The numerical value denotes tasks
              order and the stage name identifies the separate
              tasks to run in the stage.  

              The filesystem structure of the stage is:

              stage.<stage number>.<task name>

              Only 1 stage is run per invocation and the stage to be
              run is defined via required --stage flag.
 
              This program drops a pid lockfile 
              (celpprunner.<stage>.lockpid) during startup to prevent
              duplicate invocation.

              When run, this program will examine the stage and see
              if work can be done.  If stage is complete or previous
              steps have not completed, the program will exit silently.
              If previous steps have failed or current stage already 
              exists in error uncomplete state then program will report
              the error via emails set in --email flag as well as report
              via stderr/stdout and exit with nonzero exit code.  
              
              This program utilizes simple token files to denote stage
              completion.  If a stage has a:

              'complete' file - then stage is done and no other
                                checking is done.

              'error' file - then stage failed.
          
              'start' file - then stage is running.
              
              Notification of stage start and end will be sent to 
              addresses set via --email flag.
               
              Regardless of the stage specified this program will examine the
              celppdir to find the latest weekly download of data from
              wwPDB which should be under <year>/dataset.week.# path.
              This program then verifies the stage specified by --stage can
              be run.\n
              For 'blast' stage this program verifies 
              stage.1.dataimport exists and has 'complete' file.  Also
              the --blastdir path must exist and within a 'current'
              symlink/folder must exist and within a 'complete' file must
              also reside. If both conditions are met then the blast stage
              is run and output stored in stage.2.blastnfilter\n
              For 'docking' stage, this program verifies stage2.blastnfilter
              exists and has a 'complete' file within it.  If 'complete'
              this program will run fred docking and store output in
              stage.3.fred.  As new algorithms are incorporated additional
              stage.3.<algo> will be created an run.
              For 'scoring' stage, this program finds all complete 
              stage.3.<algo> folders and invokes appropriate scoring
              algorithm storing results in stage.4.<algo>.scoring
              """

    theargs = _parse_arguments(desc, sys.argv[1:])
    try:
        if os.path.basename(theargs.blastdir) is 'current':
            theargs.blastdir = os.path.dirname(theargs.blastdir)
    except AttributeError:
        pass
     
    _setup_logging(theargs)

    try:
        # get the lock
        lock = _get_lock(theargs)
        sys.exit(run_stage(theargs))

    except Exception as e:
        logger.exception("Error caught exception")
        sys.exit(2)
    finally:
        # release lock
        logger.debug('Releasing lock')
        lock.release()


if __name__ == '__main__':
    main()
