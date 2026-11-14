# File and folder names of a catalog entry, from its display name G/H[n]#k.
#
#   632/333[8]     -> slug 632-333-8      job 632_333_8      dir 632/8/632-333-8
#   333/333[3]#2   -> slug 333-333-3-2    job 333_333_3_2    dir 333/3/333-333-3-2
#   *632/*333[2]   -> slug s632-s333-2    ...                ('*' is written 's')
#
# '#k' tells apart subgroups that share G/H[n] (see catalog-layout: names are
# G/H[n]#k, #k omitted when unique); it becomes a trailing '-k' because '#'
# would start a URL fragment.  Shared by make_entry_job.py, make_entry_page.py
# and make_sheet.py so the three always agree.

def entry_names(entry_name, n):
    gsym, rest = entry_name.split('/')
    hsym = rest.split('[')[0]
    k = rest.split('#')[1] if '#' in rest else None
    tail = ('-%s' % k) if k else ''
    slug = ('%s-%s-%d%s' % (gsym, hsym, n, tail)).replace('*', 's')
    job_file = slug.replace('-', '_')
    out_dir = '%s/%d/%s' % (gsym.replace('*', 's'), n, slug)
    return {'gsym': gsym, 'hsym': hsym, 'k': k, 'slug': slug,
            'job_file': job_file, 'dir': out_dir}
