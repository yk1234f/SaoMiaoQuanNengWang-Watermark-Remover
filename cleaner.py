"""Remove only the exact independent watermark image in the supplied sample."""
from pathlib import Path
import hashlib
import os
import tempfile
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream

WATERMARK_SHA256 = '6f7426a0cccc2a257cf9128bfe56c4d8fa42076cd9ed31f02806f7b1da010c24'

def clean_pdf(source, output_dir=None):
    source = Path(source).resolve()
    if source.suffix.lower() != '.pdf':
        raise ValueError('请选择 PDF 文件')
    reader = PdfReader(source)
    if reader.is_encrypted:
        raise ValueError('加密文件，请先解除密码后重试')
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    count = 0
    for page in writer.pages:
        resources = page.get('/Resources', {})
        objects = resources.get('/XObject', {})
        if hasattr(objects, 'get_object'):
            objects = objects.get_object()
        matched = set()
        for name, ref in objects.items():
            obj = ref.get_object()
            if (obj.get('/Subtype') == '/Image' and obj.get('/Width') == 204
                    and obj.get('/Height') == 69
                    and hashlib.sha256(obj.get_data()).hexdigest() == WATERMARK_SHA256):
                matched.add(name)
        if not matched or page.get_contents() is None:
            continue
        stream = ContentStream(page.get_contents(), writer)
        kept = []
        for operands, operator in stream.operations:
            if operator == b'Do' and operands[0] in matched:
                count += 1
            else:
                kept.append((operands, operator))
        stream.operations = kept
        page.replace_contents(stream)
        for name in matched:
            del objects[name]
    if not count:
        return None, 0, len(reader.pages)
    folder = Path(output_dir) if output_dir else source.parent / '去水印输出'
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / (source.stem + '_去水印.pdf')
    serial = 2
    while destination.exists():
        destination = folder / (source.stem + f'_去水印_{serial}.pdf')
        serial += 1
    fd, temporary = tempfile.mkstemp(prefix='.pdf-clean-', suffix='.tmp', dir=folder)
    try:
        with os.fdopen(fd, 'wb') as handle:
            writer.write(handle)
        check = PdfReader(temporary)
        if len(check.pages) != len(reader.pages):
            raise RuntimeError('输出页数校验失败')
        # Windows rename is atomic and refuses to replace an existing file.
        if os.name == 'nt':
            os.rename(temporary, destination)
        else:
            os.link(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return destination, count, len(reader.pages)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('files', nargs='+')
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    for file in args.files:
        print(file, clean_pdf(file, args.output_dir))
