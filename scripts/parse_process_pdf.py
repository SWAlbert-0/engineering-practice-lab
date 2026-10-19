"""Parse only text PDFs in a bounded subprocess. Input and output are never logs."""
import io,json,sys
try:
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
    except ImportError:pass  # Windows: parent still enforces a wall-clock timeout.
    from pypdf import PdfReader
    raw=sys.stdin.buffer.read(8*1024*1024+1)
    if len(raw)>8*1024*1024:raise ValueError('PDF 超过 8 MiB。')
    reader=PdfReader(io.BytesIO(raw),strict=True)
    if reader.is_encrypted:raise ValueError('加密 PDF 暂不支持。')
    if len(reader.pages)>100:raise ValueError('PDF 最多 100 页。')
    pages=[];total=0
    for n,page in enumerate(reader.pages,1):
        content=page.get_contents()
        if content is not None and len(content.get_data())>8*1024*1024:raise ValueError('PDF 单页内容过大。')
        value=(page.extract_text() or '').strip();total+=len(value)
        if total>300000:raise ValueError('PDF 提取文本超过 30 万字。')
        if value:pages.append({'page':n,'text':value})
    if not pages:raise ValueError('PDF 没有可提取文本；扫描件 OCR 暂不支持。')
    print(json.dumps({'pages':pages},ensure_ascii=False))
except Exception as error:
    message=str(error) if isinstance(error,ValueError) else 'PDF 解析失败，请检查文件或转为 UTF-8 文本。'
    print(json.dumps({'error':message},ensure_ascii=False));sys.exit(1)
