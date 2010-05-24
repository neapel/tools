#!/usr/bin/env python

import re
from time import sleep
from subprocess import Popen
import sys
from optparse import OptionParser


cpu_mask = re.compile('cpu\d+')

# user=0, nice=1, system=2, idle=3, iowait=4, irq=5, softirq=6
IDLE_FIELD = 3

def stat():
	''' yields CPU times '''
	with open('/proc/stat', 'r') as f:
		for l in f:
			fields = l.split()
			if len(fields) > 1:
				cpu_name = fields[0]
				if  cpu_mask.match(cpu_name):
					yield cpu_name, map(float, fields[1:])

def dict_diff(a, b):
	''' returns the difference of the values by key '''
	for k in set(a.keys()).intersection(set(b.keys())):
		yield k, [ (av - bv) for av, bv in zip(a[k], b[k]) ]

def idle(interval):
	''' yields the CPU's idle time at interval '''
	old = dict(stat())
	while True:
		sleep(interval)
		new = dict(stat())
		diff = dict(dict_diff(new, old))
		yield dict([ (cpu, (times[IDLE_FIELD] / sum(times))) for cpu, times in diff.items() ])
		old = new

def avg_idle(interval):
	''' yields the average idle time over all CPUs '''
	for i in idle(interval):
		v = i.values()
		yield sum(v) / len(v)

def idle_do(f, interval, low_thresh, high_thresh, verbose):
	fmt = 'idle %.2f  '
	been_low = False
	for i in avg_idle(interval):
		if i <= low_thresh:
			print fmt % (i * 100), 'armed'
			been_low = True
		elif been_low and i >= high_thresh:
			print fmt % (i * 100), 'tripped'
			f()
			been_low = False
		elif verbose:
			print fmt % (i * 100), 'armed' if been_low else ''

def run(args):
	p = Popen(args, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
	p.communicate()

if __name__ == '__main__':
	parser = OptionParser(usage = "usage: %prog [options] command args...")

	parser.add_option('-i', '--interval', dest='interval', type='float', help='Check every X seconds (default: %default)', metavar='X', default=1.0)
	parser.add_option('-l', '--low', dest='low', type='float', help='CPU has to idle for less than L% before tripping the alarm again (default: %default)', metavar='L', default=50)
	parser.add_option('-a', '--alarm', dest='high', type='float', help='CPU has to idle for more than H% to trip the alarm (default: %default)', metavar='H', default=80)
	parser.add_option('-v', '--verbose', dest='verbose', action='store_true', help='Prints the current idle rate every interval', default=False)

	(opt, args) = parser.parse_args()

	if len(args) < 1:
		parser.error('Please supply a command (with options) to run in case of alarm. See --help')

	if opt.interval < 1:
		parser.error('Please use an interval >= 1')

	if opt.low >= opt.high:
		parser.error('Low threshold should be lower than alarm threshold')

	if opt.low < 0 or opt.low > 100 or opt.high < 0 or opt.high > 100:
		parser.error('Percentages are between 0 and 100. Values will be averaged across all CPUs')

	try:
		idle_do( lambda: run(args), opt.interval, opt.low/100, opt.high/100, opt.verbose )
	except KeyboardInterrupt:
		pass
