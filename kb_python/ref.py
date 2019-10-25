import logging
import os

from .config import get_kallisto_binary_path
from .constants import (
    COMBINED_FILENAME,
    SORTED_FASTA_FILENAME,
    SORTED_GTF_FILENAME,
)
from .fasta import FASTA
from .gtf import GTF
from .utils import (
    concatenate_files,
    generate_cdna_fasta,
    generate_intron_fasta,
    run_executable,
)

logger = logging.getLogger(__name__)


def sort_gtf(gtf_path, out_path):
    gtf = GTF(gtf_path)
    gtf.sort(out_path)
    return out_path


def sort_fasta(fasta_path, out_path):
    fasta = FASTA(fasta_path)
    fasta.sort(out_path)
    return out_path


def create_t2g_from_gtf(gtf_path, t2g_path, intron=False):
    gtf = GTF(gtf_path)
    with open(t2g_path, 'w') as f:
        for entry in gtf.entries():
            if entry['feature'] == 'transcript':
                transcript_id = entry['group']['transcript_id']
                transcript_version = entry['group'].get(
                    'transcript_version', None
                )
                transcript = '{}.{}'.format(
                    transcript_id, transcript_version
                ) if transcript_version else transcript_id
                gene_id = entry['group']['gene_id']
                gene_version = entry['group'].get('gene_version', None)
                gene = '{}.{}'.format(
                    gene_id, gene_version
                ) if gene_version else gene_id
                gene_name = entry['group'].get('gene_name', '')
                f.write('{}\t{}\t{}\n'.format(transcript, gene, gene_name))

                if intron:
                    f.write(
                        '{}\t{}\t{}\n'.format(
                            transcript + '-I', gene, gene_name
                        )
                    )

    return {'t2g': t2g_path}


def create_t2c(fasta_path, t2c_path):
    fasta = FASTA(fasta_path)
    with open(t2c_path, 'w') as f:
        for sequence_id, _ in fasta.entries():
            f.write('{}\n'.format(sequence_id))
    return {'t2c': t2c_path}


def kallisto_index(fasta_path, index_path, k=31):
    command = [
        get_kallisto_binary_path(), 'index', '-i', index_path, '-k', k,
        fasta_path
    ]
    run_executable(command)
    return {'index': index_path}


def ref(
        fasta_path,
        gtf_path,
        cdna_path,
        index_path,
        t2g_path,
        temp_dir='tmp',
        overwrite=False
):
    results = {}
    logger.info('Creating transcript-to-gene mapping at {}'.format(t2g_path))
    t2g_result = create_t2g_from_gtf(gtf_path, t2g_path)
    results.update(t2g_result)
    if not os.path.exists(index_path) or overwrite:
        logger.info('Sorting FASTA')
        sorted_fasta_path = sort_fasta(
            fasta_path, os.path.join(temp_dir, SORTED_FASTA_FILENAME)
        )
        logger.info('Sorting GTF')
        sorted_gtf_path = sort_gtf(
            gtf_path, os.path.join(temp_dir, SORTED_GTF_FILENAME)
        )
        logger.info('Splitting genome into cDNA at {}'.format(cdna_path))
        cdna_fasta_path = generate_cdna_fasta(
            sorted_fasta_path, sorted_gtf_path, cdna_path
        )

        logger.info('Indexing')
        index_result = kallisto_index(cdna_fasta_path, index_path)
        results.update(index_result)
    else:
        logger.info(
            'Skipping kallisto index because {} already exists. Use the --overwrite flag to overwrite.'
            .format(index_path)
        )
    return results


def ref_velocity(
        fasta_path,
        gtf_path,
        cdna_path,
        intron_path,
        index_path,
        t2g_path,
        cdna_t2c_path,
        intron_t2c_path,
        temp_dir='tmp',
        overwrite=False,
):
    results = {}
    logger.info('Creating transcript-to-gene mapping at {}'.format(t2g_path))
    t2g_result = create_t2g_from_gtf(gtf_path, t2g_path, intron=True)
    results.update(t2g_result)
    if not os.path.exists(index_path) or overwrite:
        logger.info('Sorting FASTA')
        sorted_fasta_path = sort_fasta(
            fasta_path, os.path.join(temp_dir, SORTED_FASTA_FILENAME)
        )
        logger.info('Sorting GTF')
        sorted_gtf_path = sort_gtf(
            gtf_path, os.path.join(temp_dir, SORTED_GTF_FILENAME)
        )
        logger.info('Splitting genome into cDNA at {}'.format(cdna_path))
        cdna_fasta_path = generate_cdna_fasta(
            sorted_fasta_path, sorted_gtf_path, cdna_path
        )
        results.update({'cdna_fasta': cdna_fasta_path})
        logger.info(
            'Creating cDNA transcripts-to-capture at {}'.format(cdna_t2c_path)
        )
        cdna_t2c_result = create_t2c(cdna_fasta_path, cdna_t2c_path)
        results.update({'cdna_t2c': cdna_t2c_result['t2c']})
        logger.info('Splitting genome into introns at {}'.format(intron_path))
        intron_fasta_path = generate_intron_fasta(
            sorted_fasta_path, sorted_gtf_path, intron_path
        )
        results.update({'intron_fasta': intron_fasta_path})
        logger.info(
            'Creating intron transcripts-to-capture at {}'.
            format(cdna_t2c_path)
        )
        intron_t2c_result = create_t2c(intron_fasta_path, intron_t2c_path)
        results.update({'intron_t2c': intron_t2c_result['t2c']})
        logger.info('Concatenating cDNA and intron FASTAs')
        combined_path = concatenate_files(
            cdna_fasta_path,
            intron_fasta_path,
            out_path=os.path.join(temp_dir, COMBINED_FILENAME),
            temp_dir=temp_dir
        )
        logger.info('Indexing')
        index_result = kallisto_index(combined_path, index_path)
        results.update(index_result)
    else:
        logger.info(
            'Skipping kallisto index because {} already exists. Use the --overwrite flag to overwrite.'
            .format(index_path)
        )

    return results
