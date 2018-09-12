import re
import sys

from django.db import models
from jsonfield import JSONField
import unicodecsv


# The default field size limit is 131072 characters
unicodecsv.field_size_limit(sys.maxsize)


class Hit(models.Model):
    """
    Human Intelligence Task
    """
    class Meta:
        verbose_name = "HIT"

    hit_batch = models.ForeignKey('HitBatch')
    completed = models.BooleanField(default=False)
    input_csv_fields = JSONField()
    answers = JSONField(blank=True)

    def __unicode__(self):
        return 'HIT id:{}'.format(self.id)

    def get_output_csv_fieldnames(self):
        return tuple(sorted(
            [u'Input.' + k for k in self.input_csv_fields.keys()] +
            [u'Answer.' + k for k in self.answers.keys()]
        ))

    def generate_form(self):
        result = self.hit_batch.hit_template.form
        for field in self.input_csv_fields.keys():
            result = result.replace(
                r'${' + field + r'}',
                self.input_csv_fields[field]
            )

        # Surround the html in the form with two div tags:
        # one surrounding the HIT in a black box
        # and the other creating some white space between the black box and the
        # form.
        border = (
            '<div style="'
            ' width:100%%;'
            ' border:2px solid black;'
            ' margin-top:10px'
            '">'
            '%s'
            '</div>'
        )
        margin = '<div style="margin:10px">%s</div>'

        result = margin % result
        result = border % result
        return result

    def save(self, *args, **kwargs):
        if 'csrfmiddlewaretoken' in self.answers:
            del self.answers['csrfmiddlewaretoken']
        super(Hit, self).save(*args, **kwargs)


class HitBatch(models.Model):
    class Meta:
        verbose_name = "HIT batch"
        verbose_name_plural = "HIT batches"

    date_published = models.DateTimeField(auto_now_add=True)
    hit_template = models.ForeignKey('HitTemplate')
    filename = models.CharField(max_length=1024)
    name = models.CharField(max_length=1024)

    def create_hits_from_csv(self, csv_fh):
        header, data_rows = self._parse_csv(csv_fh)

        num_created_hits = 0
        for row in data_rows:
            if not row:
                continue
            hit = Hit(
                hit_batch=self,
                input_csv_fields=dict(zip(header, row)),
            )
            hit.save()
            num_created_hits += 1

        sys.stderr.write('%d HITs created.\n' % num_created_hits)

    def finished_hits(self):
        """
        Returns:
            QuerySet of all Hit objects associated with this HitBatch
            that have been completed.
        """
        return self.hit_set.filter(completed=True).order_by('-id')

    def to_csv(self, csv_fh):
        """Write CSV output to file handle for every Hit in batch

        Args:
            csv_fh (file-like object): File handle for CSV output
        """
        fieldnames, rows = self._results_data(self.finished_hits())
        writer = unicodecsv.DictWriter(csv_fh, fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    def unfinished_hits(self):
        """
        Returns:
            QuerySet of all Hit objects associated with this HitBatch
            that have NOT been completed.
        """
        return self.hit_set.filter(completed=False).order_by('id')

    def _parse_csv(self, csv_fh):
        """
        Args:
            csv_fh (file-like object): File handle for CSV output

        Returns:
            A tuple where the first value is a list of strings for the
            header fieldnames, and the second value is an iterable
            that returns a list of values for the rest of the roww in
            the CSV file.
        """
        rows = unicodecsv.reader(csv_fh)
        header = rows.next()
        return header, rows

    def _results_data(self, hits):
        """
        All completed HITs must come from the same template so that they have the
        same field names.

        Args:
            hits (List of Hit objects):

        Returns:
            A tuple where the first value is a list of fieldname strings, and
            the second value is a list of dicts, where the keys to these
            dicts are the values of the fieldname strings.
        """
        fieldnames = hits[0].get_output_csv_fieldnames()

        rows = []
        for hit in hits:
            row = {}
            row.update({u'Input.' + k: v for k, v in hit.input_csv_fields.items()})
            row.update({u'Answer.' + k: v for k, v in hit.answers.items()})
            rows.append(row)

        return fieldnames, rows

    def _results_data_groups(self, hits):
        hit_fieldname_tuples = [hit.get_output_csv_fieldnames() for hit in hits]
        fieldname_tuple_id_map = dict(
            (t, i)
            for (i, t)
            in enumerate(sorted(set(hit_fieldname_tuples)))
        )

        hit_groups = [[] for t in fieldname_tuple_id_map]
        for (hit, fieldnames) in zip(completed_hits, hit_fieldname_tuples):
            i = fieldname_tuple_id_map[fieldnames]
            hit_groups[i].append(hit)

        sys.stderr.write("_results_data_groups(): %s" % str(map(results_data, hit_groups)))
        return map(results_data, hit_groups)

    def __unicode__(self):
        return 'HIT Batch: {}'.format(self.name)


class HitTemplate(models.Model):
    class Meta:
        verbose_name = "HIT template"

    filename = models.CharField(max_length=1024)
    name = models.CharField(max_length=1024)
    form = models.TextField()
    date_modified = models.DateTimeField(auto_now=True)

    # Fieldnames are automatically extracted from form text
    fieldnames = JSONField(blank=True)

    def save(self, *args, **kwargs):
        # Extract fieldnames from form text, save fieldnames as keys of JSON dict
        unique_fieldnames = set(re.findall(r'\${(\w+)}', self.form))
        self.fieldnames = dict((fn, True) for fn in unique_fieldnames)
        super(HitTemplate, self).save(*args, **kwargs)

    def to_csv(self, csv_fh):
        """
        Writes CSV output to file handle for every Hit associated with template

        Args:
            csv_fh (file-like object): File handle for CSV output
        """
        batches = self.hitbatch_set.all()
        if batches:
            fieldnames, rows = batches[0]._results_data(batches[0].finished_hits())
            writer = unicodecsv.DictWriter(csv_fh, fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
            for batch in batches[1:]:
                _, rows = batch._results_data(batch.finished_hits())
                for row in rows:
                    writer.writerow(row)

    def __unicode__(self):
        return 'HIT Template: {}'.format(self.name)
