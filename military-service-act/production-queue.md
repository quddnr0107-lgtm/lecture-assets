# 병역법 제80회 대본 기준 도식 작업

내용 기준은 **기존 제80회(27년 전반기) 병역법 강의 대본 166편**입니다. 2027-02-02는 요청된 학습 법령 기준일이며, 확정 시험일을 뜻하지 않습니다.

기존 도식 **283장은 공개된 상태**입니다. 대본 전문과의 일치 여부와 중요한 설명의 누락 여부를 확인하는 강의별 검토 166건 중 13강은 검토 완료, 153강은 대기 중입니다. 대본 전체 범위의 제작이 끝났다고 표시하지 않습니다.

## 진행 방법

1. 고정된 원본 대본을 처음부터 끝까지 읽고, 등록된 파일 경로와 blob SHA를 확인합니다.
2. 대본과 맞는 기존 도식은 사용하고, 어긋난 부분은 교정합니다.
3. 대본에 실제로 있는 중요한 흐름·비교가 기존 도식에서 빠진 경우에만 추가합니다. 추가 이미지 수는 검토 후 결정합니다.
4. 대본 대응, 문장 의미, 화면 가독성을 확인하고 도식·목록·문서·갤러리·근거를 함께 정리합니다.

**77강·94강·109강부터 우선 검토**합니다. 이 우선순위가 새 도식이나 추가 장수를 미리 확정하는 것은 아닙니다. 외부 법령을 별도 생산 기준으로 삼거나, 대본에 없는 내용을 확대하지 않습니다.

## 이전 계획과 기록

이전의 **법령 확장 후보 299건과 재사용 검토 4건은 현재 제작계획에서 철회**했습니다. 303건은 당시의 후보 작업 수이며, 제작해야 할 이미지 303장을 뜻하지 않습니다. 기존 기록은 [이전 계획 보존본](production-history/law-expansion-queue-20261127.superseded.json)에 남깁니다.

## 작업 관리

실제로 사용할 수 있는 최대 병렬 작업 수로 강의별 검토를 진행하고, 한 조정자가 공용 목록과 공개 반영을 관리합니다. 기존 도식 번호와 경로는 유지합니다. 게시 직전에 새 작업 세대와 대본 기준이 일치하는지 확인하여 이전 기준의 결과는 반영하지 않습니다.

대본 전문은 공개하지 않습니다. [대본 출처 목록](script-sources-exam80.json)의 경로·해시와 필요한 도식 대응 근거만 사용합니다. 166강 검토가 끝나면 재사용·교정·추가 결과를 구분하여 보고하고 반복 실행을 마칩니다.

## 2026-11-27 원고 대조 체크포인트
- MS-143: 기존 도식 재사용 완료. [근거](production-evidence/exam80-generation-2/MS-143/001-c04f5f4a9a57a60177be60e8c4f238651f6566fa6806cb3096fa0213cb17fdbb.json)
- MS-145: 기존 도식 재사용 완료. [근거](production-evidence/exam80-generation-2/MS-145/001-ac6d2dcb37959bd8f5a1bf799bfe29fcf72207b4021c4d336edc8d2620f20948.json)
- MS-160: 기존 도식 재사용 완료. [근거](production-evidence/exam80-generation-2/MS-160/001-4fd667774affd36c7216d777d3ad815292381f91e737a95b7cda1efaa973b98c.json)

## MS-077 추가 초안 체크포인트
- 원고 전문 대조 완료, 추가 SVG 초안 7장 및 로컬 무손실 WebP 7장 렌더 검사. 기존 초안과 구분해 [검수 근거](production-evidence/exam80-generation-2/draft-batches/20261127-02/checkpoint.json)에 보관합니다.
- WebP 공개 반영 및 최종 목록 일치 전까지 MS-077은 대기 상태입니다. 신규 확정 이미지 수에는 포함하지 않습니다.

## 2026-11-27 추가 원고 대조 체크포인트
- MS-137: 기존 도식 재사용 완료. [근거](production-evidence/exam80-generation-2/MS-137/001-ec420b7d8a5bb1d8b782f0ac819afca21ab1baa8c2189888e4c16bb69b6a1685.json)
- MS-150: 기존 도식 재사용 완료. [근거](production-evidence/exam80-generation-2/MS-150/001-30f90ad54f38cc9a0908a3454036914b1c05972c1e917d43393612669b49bec9.json)
- MS-154: 기존 도식 재사용 완료. [근거](production-evidence/exam80-generation-2/MS-154/001-5132d7f38321b48a9d17459441c221fee5f48e8f70f11bb2e366287e792ed7d8.json)

## 77강 도식 공개 체크포인트
- 렌더링된 초안 10장 중 9장을 원고 대조·공개 WebP 시각 검수 및 SHA-256 검증 후 정식 경로와 목록에 반영. [검수 근거](production-evidence/exam80-generation-2/MS-077/003-publication-review.json)
- 군 필요인원 통보 도식은 원고 181행의 인원 배정 주체와 어긋나므로 정식 공개에서 제외. 77강 전체 검수는 대기 상태 유지.
- 기존 283장 + 신규 9장 = 공개 292장. 전체 강의 검수 완료 6강, 대기 160강.

## 94강·109강 도식 공개 체크포인트
- 기존 원고와 대조한 4장(각 2장)을 정식 SVG·무손실 WebP 경로로 반영했습니다. [94강 근거](production-evidence/exam80-generation-2/MS-094/002-publication-review.json) · [109강 근거](production-evidence/exam80-generation-2/MS-109/002-publication-review.json).
- 공개 도식 296장(기존 283장 + 보완 13장). 전체 강의 검수 6강 완료, 160강 대기. 해당 강의 전체 검수는 아직 완료가 아닙니다.

## 77·94·109강 추가 초안
- 배정 주체 교정 1장 및 추가 도식 6장을 SVG 초안으로 저장. [검수 대기 체크포인트](production-evidence/exam80-generation-2/draft-batches/20261127-02/checkpoint-03.json). 공개 확정 수에는 미포함.

## 후속 7장 WebP 검수 체크포인트
- 7장 렌더링 결과 공개 경로의 실제 화면 확인. 3장 원고 대조 통과(군 필요인원 통보·필요인원 통보 기준·국외 거주 허가 간주), 4장 교정 필요.
- 정식 경로, 편집 데이터·manifest 동시 갱신 및 SHA-256 재계산 전까지 신규 확정 이미지로 세지 않음. [검수 근거](production-evidence/exam80-generation-2/draft-batches/20261127-02/checkpoint-04-visual-review.json).
- 전체 강의 검수 6강 완료, 160강 대기. 기존 공개 도식 296장 유지.

## 후속 교정 체크포인트 05
- 94강 2장·109강 3장 SVG 교정본 저장. 원고 267행의 취소 간주/병역의무 부과 재량을 다시 확인하여 109강의 기존 통과 초안도 교정 대상으로 변경.
- 77강·94강 검수 통과 초안 각 1장은 정식 파일·목록 통합 대기. 교정본 5장은 WebP 렌더링 및 시각 검수 대기. 정식 공개 수 296장 유지. [근거](production-evidence/exam80-generation-2/draft-batches/20261127-02/checkpoint-05-corrected-drafts.json).

## 후속 도식 정식 공개 체크포인트 06
- 77강 1장, 94강 3장, 109강 3장: 원고 근거 재대조, 실제 WebP 화면 및 1600×1120 VP8L 헤더와 SHA-256 검증. 정식 파일·편집 데이터·강의별/전체 목록·갤러리·검수 기록 통합.
- 기존 283장 + 신규 보완 20장 = 공개 303장. 전체 강의 검수 6강 완료, 160강 대기. 우선 3강의 전체 원고 설명 대응 검수는 아직 완료하지 않음.
- 근거: [MS-077](production-evidence/exam80-generation-2/MS-077/006-publication-review.json) · [MS-094](production-evidence/exam80-generation-2/MS-094/006-publication-review.json) · [MS-109](production-evidence/exam80-generation-2/MS-109/006-publication-review.json).

## 추가 원고 대조 체크포인트 07
- MS-004: 기존 도식 재사용 완료. [근거](production-evidence/exam80-generation-2/MS-004/001-0fa030fc0065b6dfb76edd27d35d04515a845b646c33154a3d53d73a2d3ccabb.json)
- MS-052: 기존 도식 재사용 완료. [근거](production-evidence/exam80-generation-2/MS-052/001-2840c8f383e3c0f908eb12f189b0e769537146a2c300e5c863fa9190d43e6f52.json)
- 전체 8강 완료, 158강 대기. 이미지 추가·수정 없음.

## 원고 범위 검수·도식 초안 체크포인트 07
- 6장 SVG 초안 (5장 추가 후보, 1장 교정 후보). 기존 원고 전문·blob SHA 대조 후 저장. 렌더링 및 시각검수 전에는 정식 수량에 포함하지 않음.
- [검수 근거 및 대상 ID](production-evidence/exam80-generation-2/draft-batches/20261127-02/checkpoint-07-coverage-drafts.json) · 전체 8강 완료, 158강 대기. 기존 공개 303장 유지.

## 정식 공개 체크포인트 08
- 신규 도식 5장 및 77강 전직 도식 1장 교정. SVG와 실제 1600×1120 무손실 WebP의 해시 및 화면 검수.
- 10·117·157강은 기존 도식과 신규 도식의 원고 전체 핵심 대응 검토 완료. 77강은 전체 범위 대조 대기.
- 공개 308장, 전체 11강 완료, 155강 대기. 근거: [MS-010](production-evidence/exam80-generation-2/MS-010/008-publication-review.json) · [MS-077](production-evidence/exam80-generation-2/MS-077/008-publication-review.json) · [MS-117](production-evidence/exam80-generation-2/MS-117/008-publication-review.json) · [MS-157](production-evidence/exam80-generation-2/MS-157/008-publication-review.json)

## 109강 원고 범위 체크포인트 09
- 기존 8장과 원고 전문을 대조하여 제한 대상·예외, 허가 사유, 나머지 취소 사유, 37세 간주 사유, 임기제공무원 유보의 신규 SVG 초안 5장 작성. [근거](production-evidence/exam80-generation-2/draft-batches/20261127-02/checkpoint-09-MS-109-coverage-drafts.json).
- 원고의 복무 중 대상 제외 적용 범위는 불명확하여 추정하지 않음. WebP 렌더·시각 검수와 최종 통합 전까지 정식 수량은 308장, 전체 11강 완료·155강 대기 유지.

## 109강 정식 공개 체크포인트 10
- D10~D13 신규 4장 원고·실제 WebP 화면 및 해시 검수 후 정식 통합. D09는 제외 적용 범위와 주체 명확화 필요로 보류. [근거](production-evidence/exam80-generation-2/MS-109/010-publication-review.json).
- 공개 312장, 11강 완료·155강 대기. 전체 109강 검수 완료는 아님.

## 2026-11-28 원고 대조 체크포인트 11
- MS-048: 기존 도식 재사용 완료. [근거](production-evidence/exam80-generation-2/MS-048/001-c7065f3e98f2f9acd4bc8753ee918691cebcc8c0d2b622d23e0d774eaea2baf8.json)
- MS-049: 기존 도식 재사용 완료. [근거](production-evidence/exam80-generation-2/MS-049/001-502ad3e8e7009e757fd46eb3a1c768c3ba211a9a010a556415ffabe2ad460959.json)
- 전체 13강 완료, 153강 대기. 공개 이미지 312장 유지.
