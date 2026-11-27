# 훈령 도식 제작 원본

[78강 전체 목록](../README.md)에서 강의별 이미지를 볼 수 있습니다.

`diagrams.source.json`은 원고·조문 근거, `layout-qa.json`은 렌더링 검사 결과입니다.

## 다시 만들기

저장소 루트에서 Python 3, Pillow, Inkscape 및 Noto Sans CJK 서체가 설치된 환경을 사용합니다.

```bash
python tools/render_directive_diagrams.py defense-directives/diagrams/diagrams.source.json
```
