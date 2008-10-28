
import time


def timeit(n, func, *args):
    runs = []
    for n in range(0, n):
        start = time.clock()
        func.__call__(*args)
        runs.append(time.clock() - start)
    avg = sum(runs)/len(runs)
    print "%1.4f seconds" % avg
