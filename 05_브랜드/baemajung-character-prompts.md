# 배마중 캐릭터 아이콘 · 로고 제작 프롬프트

## 결과 파일

- `baemajung-icon.png`: 1254 × 1254, RGBA PNG. 입 없는 어선 캐릭터, 청록색 둥근 사각형 포함. 사각형 바깥은 투명.
- `baemajung-wordmark.png`: 2172 × 724, RGBA PNG. ‘배마중’ 로고 글씨 + 파도 밑줄 + 산호색 포인트. 배경과 글자 내부의 빈 공간은 투명.
- 원본 시안: `baemajung-character-no-mouth.png`. 원본과 실제 앱 소스는 변경하지 않음.

제작 도구는 기본 내장 이미지 생성 도구(image_gen)입니다. 아래 1·2·4·5는 실제 사용한 프롬프트이고, 3은 다른 아이콘을 같은 분위기로 만들기 위해 정리한 재사용 템플릿입니다. 이미지 생성 기반 분리이므로 픽셀 단위의 원본 크롭과는 차이가 있을 수 있습니다.

‘배마중’ 글씨는 이 이름을 위해 만든 **로고 레터링 이미지**입니다. 설치 가능한 전체 글꼴 파일(TTF/WOFF)이 아닙니다. 원래 프롬프트의 Jua-like / Pretendard-like는 시각적 방향을 지정한 표현이며, 이미지에 실제 웹폰트가 적용되었다는 뜻은 아닙니다.

## 1. 처음 캐릭터 아이콘과 로고·화면 글씨를 함께 만든 프롬프트

사용자가 제공한 `어선1.jpg`, `어선2.jpg`, `어선3.jpeg`, `어선4.jpg` 네 장을 구조와 분위기 레퍼런스로 함께 전달했습니다. 사진 자체를 수정한 것이 아니라 새로운 시안을 생성했습니다. 이 최초 프롬프트에는 입이 있었고, 아래 2번으로 입만 제거했습니다.

```text
Use case: logo-brand.
Create a finished, beautifully art-directed premium brand concept presentation for the Korean service "배마중", a Guryongpo fishing-harbor arrival forecasting and fish-notification app for fish market buyers and restaurant owners.
Input images: ALL four images are STRUCTURAL AND MOOD REFERENCES ONLY, NOT EDIT TARGETS. Design an ORIGINAL Korean working fishing boat using their recognizable raised curved bow, compact wheelhouse, open fishing deck, mast/radar, rubber tire fenders, and working-boat silhouette. Do not reproduce the photos, their ocean backgrounds, watermarks, or vessel identity.
Output: one complete landscape 3:2 branding board with exceptional sharpness, generous editorial spacing and readable Korean typography, on an opaque warm pale sea-gray paper background. This is a design preview, not a screenshot of an implemented app.
Board layout: left 55% a prominent detailed 3D app icon and original Korean wordmark lockup "배마중", ample breathing room, plus a small repetition of the icon at header size; right 45% a restrained typography and mobile app excerpt. Include a small eyebrow "배마중" and the concept name. Do not make a busy infographic or multiple alternate designs on the same board.
Brand design must include custom-styled Korean logo lettering "배마중" (exact characters 배 / 마 / 중), polished spacing and optical balance, not just an arbitrary generic font. Also demonstrate distinct UI hierarchy: a readable Korean heading, body, large tabular-looking time/countdown numerals, and compact labels. Typography in the app must be highly legible and believable. Include only these exact minimal texts, no extra tiny filler:
"배마중"
"구룡포 새벽 입항·어종 알림"
"들어오는 배"  "알림"  "물어보기"
"20"  "분 뒤 도착"  "05:20"
"남진호"
"붉은대게 가능성이 높아요"
"어종 추정 · 입항 예보"
"생선 알림 받기"
"기다리는 생선이 있나요?"
"원하는 생선이 들어오면 먼저 알려 드릴게요."
UI excerpt structure: quiet sea-gray header with small boat icon + wordmark and "05:00", white rounded bottom-sheet-style card with the three tabs, coral large "20" beside "분 뒤 도착" and "05:20", dark boat name and fish forecast, muted uncertainty note, one soft gray-green notification button. Maintain ample margins and sensible real app text sizes. Do NOT show prices, fake precise forecasts, an invented dashboard, map, chat conversation, or phone hardware.
The palette should harmonize with the existing service: deep harbor teal #0c5560, ivory white, mist #eef3f2, warm coral #e8604c, countdown text #c0392b, dark ink #10232b.
Avoid: flat vector icons, geometric pictograms, silhouettes as the primary art, generic sailboats, yachts, cruise ships, cartoon fish, copied photographs, excessive fine rigging, plastic clip-art, logos of existing companies, watermarks, Latin brand names, and fake font names.
Concept name (exact visible text): "마중이".
Style of primary icon: an original lovable 3D Korean fishing-boat mascot, made from beautifully rendered matte painted wood/resin/clay-like materials, NOT a flat cartoon. Retain the functional high bow, stout working hull, a small wheelhouse with windows, compact radar mast, open teal fishing deck, and rubber tire fenders from the Korean boat references. Chubby compact proportions and a softly upward-curved rounded bow; use the two front wheelhouse windows as expressive friendly eyes, a very subtle welcoming smile integrated into the bow. No arms, no legs, no human sailor. This must instantly read as a real local working fishing boat given gentle personality, not a whale or generic toy ship. Cream-white hull, deep teal cabin, restrained coral roof/rim, cute black fenders, carefully rendered highlights, subtle texture, gorgeous soft shadows, excellent three-quarter composition. Fit fully inside a soft rounded sea-green square icon with a small sculpted wave base, no photo background or huge ocean scene. Appeal to adult fish-market buyers as well as tourists: friendly, dependable, calm, not babyish.
Logo lettering: custom warm Korean lettering "배마중", rounded chunky strokes, restrained playful buoyant rhythm in the baseline, clear open counters, lovely professional optical kerning; Jua-like friendliness polished into a distinctive wordmark. Deep teal. Do not distort readability or replace Korean characters with drawings. Keep the UI headings mildly rounded and body/numerals clean Pretendard-like sans for excellent readability, rather than using mascot display lettering for every text line. The smaller heading/body sample on the brand side uses the exact notification texts above. This board should feel welcoming and charming with high-quality volumetric rendering, completely distinct from the realistic miniature concept.
```

## 2. 승인 시안에서 입 모양을 제거한 실제 수정 프롬프트

입이 있는 `baemajung-character-v2.png`를 편집 대상으로 전달했습니다.

```text
Use case: precise-object-edit. The supplied image is the EDIT TARGET, a finished 1536x1024 Korean branding board. Make exactly one narrowly localized change: REMOVE the small black curved smiling mouth from the ivory-white bow of the large character fishing boat in the left app icon. Restore the underlying white painted boat hull there, seamlessly continuing its existing horizontal plank/seam detail, subtle weathering, texture, lighting and curvature. Also remove that same mouth, if visible, from the small matching app icon in the upper-right header. Keep the two expressive eyes and eyebrows unchanged. Preserve EVERYTHING ELSE exactly: boat identity and proportions, angle, wheelhouse, all ropes, radar/mast, railings, tire fenders, coral trim, water/waves, teal rounded-square icon backing, shadows, the Korean wordmark "배마중" and its wave underline and coral accent, all typography and all exact Korean text, right-side UI, colors, layout, image dimensions and framing. Do not redesign, redraw or restyle the board. No mouth replacement, no new facial expression, no added marks. Output the entire original board with only the boat mouth retouched away.
```

## 3. 같은 분위기의 다른 아이콘을 만드는 재사용 템플릿

`baemajung-icon.png`를 스타일 레퍼런스로 첨부하고, 아래 Subject의 대괄호 부분을 원하는 대상으로 바꾸세요. 다른 대상에는 어선 구조 조건을 적용하지 않고 재질·색·조명·입체감만 맞춥니다. 승인 아이콘을 함께 넣어야 프롬프트만 쓸 때보다 시리즈의 일관성을 유지하기 쉽습니다.

```text
Use case: logo-brand.
Create ONE premium three-dimensional app icon for the Korean harbor service "배마중".
Subject: [REPLACE THIS WITH THE ICON SUBJECT, e.g. a Korean working fishing boat, a notification bell with a subtle wave detail, a fresh fish, or a small delivery truck].
Reference image: attach the approved baemajung-icon.png as a STYLE REFERENCE. Match its tactile painted materials, rounded sculptural forms, subtle weathering, material depth, lighting direction, teal/coral/ivory palette and premium miniature rendering. Design the requested subject, not a copy of the reference boat.
Composition: a clear, substantial three-quarter view, centered in a teal softly rounded square app-icon tile, approximately 3% transparent safety margin. Keep the entire subject inside the tile. Use convincing volume, gentle contact shadows, controlled highlights and a silhouette that remains readable at small sizes. Restrict tiny details to functional ones.
Palette: deep harbor teal #0c5560, sea teal, cream-white, restrained warm coral #e8604c, natural black rubber or metal only where appropriate.
Mood: friendly, dependable and locally rooted; suitable for adult fish-market buyers, not babyish.
For a boat subject: retain the raised curved bow, working deck, compact wheelhouse, radar mast, ropes and black tire fenders of a Korean coastal fishing boat. The two front wheelhouse windows may be expressive eyes. NO MOUTH, no smile on the hull, no arms, no legs.
Background: KEEP the teal rounded-square tile itself; make everything outside its rounded corners genuinely transparent.
Output: one isolated high-resolution PNG with real alpha transparency. No text, no wordmark, no subtitle, no presentation board, no UI mockup, no painted checkerboard.
Avoid flat vectors, generic geometric pictograms, silhouettes, sailboats, cruise ships, copied photography, excessive fine rigging and cheap plastic clip-art.
```

### 같은 느낌의 다른 로고 글씨를 만드는 템플릿

`baemajung-wordmark.png`를 함께 첨부하고 브랜드명만 바꾸세요. 기존 ‘배마중’ 로고 자체를 사용하려면 다시 생성하지 않고 제공한 PNG를 그대로 사용하는 것이 형태를 가장 정확히 유지합니다.

```text
Use case: logo-brand.
Reference image: attach baemajung-wordmark.png as the approved lettering/style reference.
Create an isolated Korean logo wordmark for "[REPLACE WITH THE EXACT BRAND NAME]".
Use thick rounded dark harbor-teal custom Korean lettering, open clear counters, a gently buoyant rhythm and restrained playful tilts. Give the syllables professional optical kerning; preserve the exact requested Korean spelling.
Use a tasteful flowing teal wave underline beneath the middle of the name and two small warm-coral splash accents near its upper-right. Match the approved reference's visual weight and friendly adult tone. Do not put illustrations inside the letters or sacrifice readability.
Colors: deep harbor teal #0c5560 and warm coral #e8604c.
Output: high-resolution wide transparent PNG; genuine alpha around the logo and within letter counters. Include only the lettering, wave underline and two coral accents. No background, no boat, no subtitle, no UI, no shadow and no extra text.
```

## 4. 이번 어선 아이콘 분리에 실제 사용한 프롬프트

`baemajung-character-no-mouth.png`를 편집 대상으로 전달하고 `transparent_background: true`로 생성했습니다.

```text
Use case: background-extraction. Input image is an EDIT TARGET, not a style inspiration. Extract ONLY the large rounded-square app icon from the upper LEFT of the provided branding board as a separate high-resolution square PNG asset. Preserve the original icon faithfully: the exact three-quarter character Korean fishing boat with two wheelhouse eyes and eyebrows, NO MOUTH anywhere on the hull, cream-white weathered painted hull, coral rim/roof, teal keel, radar mast, ropes, four visible black tire fenders, white and teal sculpted waves, existing teal rounded-square backing, original camera angle, rendering, textures, lighting and proportions. KEEP the teal rounded-square backing INSIDE the icon and its gently rounded corners. Everything OUTSIDE the rounded square must be genuine transparent alpha, including the corners; remove the branding board's pale background and all board graphics. Keep an approximately 3% transparent safety margin, center the icon and show its entire shape without cutting the mast or bottom. Remove all wordmarks, text, subtitles, UI cards, header mini-icon and labels. Do not introduce or restore a smiling mouth. Do not redesign or simplify the existing boat, do not create a different vessel or change the eyes. Output only this one isolated app-icon asset on a genuinely transparent background, not a checkerboard painted into the image.
```

## 5. 이번 투명 배경 로고 분리에 실제 사용한 프롬프트

같은 승인 시안을 편집 대상으로 전달하고 `transparent_background: true`로 생성했습니다.

```text
Use case: background-extraction. Input image is an EDIT TARGET. Extract ONLY the LARGE original Korean logo wordmark from the LOWER LEFT of the supplied board into a separate high-resolution transparent PNG. Preserve this precise approved lettering as faithfully as possible: "배마중" (three exact syllables 배 / 마 / 중), deep dark harbor teal thick rounded custom letter shapes, original buoyant baseline and slightly playful tilts, original relative spacing and original proportions, the teal flowing wave underline beneath the middle of the word, and the two warm coral splash/teardrop accent strokes at the upper-right of the final character. Keep ALL of these logo components together. Interior counters/holes within letters must be genuine transparent alpha as well. Remove EVERYTHING ELSE: boat, app icon, background, pale board color, right-side UI, all shadows behind the wordmark, and the gray Korean subtitle "구룡포 새벽 입항·어종 알림". Do not include that subtitle or any other text. Do not reinterpret the typeface, replace it with a generic typed font, add a mouth, change the letter silhouettes or flatten/rearrange the flowing wave underline. Center the full isolated wordmark in a wide horizontal canvas, about 3:1, with a modest clean transparent margin and NO clipped accent droplets. Output the exact existing logo as an isolated PNG with genuinely transparent background, no opaque white rectangle and no painted checkerboard.
```

