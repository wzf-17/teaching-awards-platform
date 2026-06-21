from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED


OUTPUT_PATH = Path(r"C:\Users\吴\Desktop\交底书.docx")


def make_paragraph(text: str = "", *, bold: bool = False, center: bool = False, size: int = 21) -> str:
    p_pr = []
    if center:
        p_pr.append('<w:jc w:val="center"/>')
    p_pr.append('<w:spacing w:after="120" w:line="300" w:lineRule="auto"/>')
    p_pr_xml = f"<w:pPr>{''.join(p_pr)}</w:pPr>"

    if text == "":
        return f"<w:p>{p_pr_xml}</w:p>"

    r_pr = [
        '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="宋体"/>',
        f'<w:sz w:val="{size}"/>',
        f'<w:szCs w:val="{size}"/>',
    ]
    if bold:
        r_pr.append("<w:b/>")

    run = (
        "<w:r>"
        f"<w:rPr>{''.join(r_pr)}</w:rPr>"
        f'<w:t xml:space="preserve">{escape(text)}</w:t>'
        "</w:r>"
    )
    return f"<w:p>{p_pr_xml}{run}</w:p>"


def build_document_xml(paragraphs: list[dict[str, object]]) -> str:
    body = []
    for item in paragraphs:
        body.append(
            make_paragraph(
                str(item.get("text", "")),
                bold=bool(item.get("bold", False)),
                center=bool(item.get("center", False)),
                size=int(item.get("size", 21)),
            )
        )

    sect_pr = """
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1800" w:bottom="1440" w:left="1800" w:header="851" w:footer="992" w:gutter="0"/>
      <w:cols w:space="425"/>
      <w:docGrid w:linePitch="312"/>
    </w:sectPr>
    """

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas"
 xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"
 xmlns:v="urn:schemas-microsoft-com:vml"
 xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
 xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
 xmlns:w10="urn:schemas-microsoft-com:office:word"
 xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
 xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"
 xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk"
 xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml"
 xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
 mc:Ignorable="w14 wp14">
  <w:body>
    {''.join(body)}
    {sect_pr}
  </w:body>
</w:document>"""


def build_styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
    <w:rPr>
      <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="宋体"/>
      <w:sz w:val="21"/>
      <w:szCs w:val="21"/>
    </w:rPr>
  </w:style>
</w:styles>"""


def build_core_xml() -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:dcmitype="http://purl.org/dc/dcmitype/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>交底书</dc:title>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>"""


def build_app_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft Office Word</Application>
</Properties>"""


def build_content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""


def build_root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def build_document_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>"""


def build_paragraphs() -> list[dict[str, object]]:
    paras: list[dict[str, object]] = []

    def add(text: str, *, bold: bool = False, center: bool = False, size: int = 21) -> None:
        paras.append({"text": text, "bold": bold, "center": center, "size": size})

    add("技术交底书", bold=True, center=True, size=32)
    add("2026年4月9日", center=True, size=24)
    add("")
    add("发明名称", bold=True, size=24)
    add("一种融合可视化检索与大模型智能问答的教学成果奖数据分析系统")
    add("发明人", bold=True, size=24)
    add("待填写")
    add("材料撰写人", bold=True, size=24)
    add("待填写")
    add("撰写人电话", bold=True, size=24)
    add("待填写")
    add("对申报时间有无要求？", bold=True, size=24)
    add("无            有")
    add("中、英文关键字", bold=True, size=24)
    add("教学成果奖数据分析、多维可视化检索、对比分析、大模型智能问答、上下文感知问答、教育决策支持")
    add("Teaching Achievement Award Data Analysis, Multi-dimensional Visual Retrieval, Comparative Analysis, Large-model Intelligent Question Answering, Context-aware QA, Educational Decision Support")
    add("发明人所属部门", bold=True, size=24)
    add("待填写")
    add("本专利申请所属的项目", bold=True, size=24)
    add("待填写")
    add("所属项目所处的阶段", bold=True, size=24)
    add("原型验证/应用示范")
    add("交底书撰写注意事项：", bold=True, size=24)
    add("1、专利法保护的是技术方案而非单纯功能描述，因此需明确给出系统结构、数据流程、交互机制和实现路径。")
    add("2、为了获得较大的保护范围，在能够实现本发明目的的前提下，应尽量提供可替换的数据源、模型、数据库、中间件和前端交互方案。")
    add("3、同一技术术语在全文中尽量保持统一，例如“查询卡片”“上下文摘要”“同类型对比”“智能问答路由”等，不应混用。")
    add("4、代理人或知识产权专员并非系统开发者，在沟通时应配合解释数据链路、模型调用链路和可视化联动关系。")

    add("一、缩略语和关键术语定义", bold=True, size=24)
    add("教学成果奖数据：指围绕高等教育教学成果奖形成的结构化或半结构化数据，至少包括年份、层次、类别、研究主题、学校层次、地域分布、学科类型、完成人合作情况及成果完成模式等字段。")
    add("可视化检索：指用户通过年份和分析类型等条件发起查询后，系统将结果自动组织为柱状图、饼图、表格、词云图等可视化视图的过程。")
    add("查询卡片：指承载单次独立分析任务的前端交互单元，每张卡片均具备查询、结果展示、下载和参与对比的能力。")
    add("同类型对比：指当两张查询卡片的分析类型一致时，系统自动对两次结果进行类别对齐、数值对齐并生成统一对比视图的机制。")
    add("上下文摘要：指系统在每次查询后自动从结果中提取出的结构化描述信息，至少包括查询年份、分析类型、主要类别、计数、占比、热点项和标题信息。")
    add("大模型智能问答：指基于大语言模型，在结合查询上下文摘要、多轮会话状态和平台领域知识的基础上，生成分析结论、趋势解释、标题建议或问答回复的处理过程。")
    add("问答路由：指系统根据用户问题是否涉及当前数据、是否属于解释型问题或泛化型问题，对问答请求选择不同提示模板和数据上下文注入方式的技术机制。")
    add("流式输出：指大模型生成文本后，系统以增量传输和逐段展示的方式输出问答结果，而非待全部文本生成完成后一次性显示。")

    add("二、详细介绍技术背景", bold=True, size=24)
    add("随着高等教育治理数字化和教育评价体系的持续完善，教学成果奖相关数据的统计分析需求不断增加。高校管理部门、学院、教师及研究人员往往需要围绕历届教学成果奖数据进行趋势分析、地域分布分析、学科结构分析、研究主题分析以及成果组织模式分析，以支撑政策研判、申报准备、选题规划和经验总结。")
    add("现阶段，教学成果奖数据通常分散在历届公示文件、Excel统计表、数据库表和人工整理文档中，数据格式不统一、字段命名不一致、主题描述粒度不一致的问题较为突出。用户若想完成一项完整分析，往往需要先手工检索，再复制到电子表格中二次整理，随后生成图表并撰写文字结论，整体工作流程繁琐，且难以支撑高频的交互式分析需求。")
    add("另一方面，通用的大模型智能问答技术虽然具备较强的自然语言生成能力，但如果缺少结构化数据支撑，则容易出现回答与当前查询内容不一致、无法准确引用统计结果、对“刚刚查询的内容”理解偏差较大等问题。尤其是在教育管理场景中，用户提出的问题既可能是“2021年与2025年地理位置分布差异是什么”这类强数据依赖问题，也可能是“结合热门研究主题推荐若干申报标题”这类需要综合数据线索与模型推理能力的问题。若系统无法对不同问题类型进行区分处理，则要么回答过于机械，要么缺乏数据依据。")
    add("因此，迫切需要一种能够将教学成果奖历史数据整合、标准化、可视化检索、同类型对比分析和大模型智能问答有机融合在一起的分析系统。该系统不仅应支持面向不同年份和不同维度的灵活查询，还应具备对查询结果自动生成摘要、对用户当前语境进行识别、对大模型问答进行数据绑定和路由控制的能力，从而同时兼顾统计严谨性和自然语言交互效率。")

    add("三、与本专利申请最接近的现有技术", bold=True, size=24)
    add("1 现有技术的实现方案", bold=True, size=24)
    add("现有的相关技术方案主要包括两类。第一类是基于关系数据库和可视化图表的统计分析平台。该类系统通常由前端页面、后端查询服务和数据库组成，用户通过页面选择年份、类别或机构等条件，后端根据预设SQL语句检索数据库，并将结果转换为柱状图或饼图显示。此类方案能够实现基础统计展示，但一般采用单页面单结果视图，查询结果之间相互割裂，用户需要来回切换不同页面或覆盖原有结果，难以在同一工作界面下并行保留多个分析视角。")
    add("第二类是通用的大模型问答系统或知识库问答系统。该类系统通常接受用户输入的问题，再调用大模型或检索增强模块生成回答。当接入教育领域时，多数方案仅将静态背景材料或少量文本摘要注入提示词，缺少与当前可视化查询结果的联动，无法准确感知用户刚刚查询的是哪一个维度、哪一个年份或哪一类结果。用户一旦使用诸如“这张表”“刚刚查询的结果”“上述主题”等代词提问，系统很容易出现上下文绑定错误。")
    add("上述两类技术虽然分别解决了数据展示和自然语言问答中的部分问题，但尚未形成一套完整的、可在教学成果奖场景中直接使用的“查询—对比—摘要—问答—导出”闭环系统。")
    add("图1  现有统计分析平台与通用问答系统分离架构示意图")
    add("【插图位置：图1 现有统计分析平台与通用问答系统分离架构示意图】")
    add("技术详细实现方面，传统统计平台一般将每一种分析维度对应为独立的后端接口，接口返回固定格式的JSON数组或表格数据；前端再根据预先设定的图表模板进行渲染。通用问答系统则通常直接向大模型提交用户问题及历史消息，最多附带一段静态知识背景，缺乏针对“最近查询结果”的专门上下文构建机制，也没有针对数据型问题与泛化型问题的路由策略。")
    add("2 现有技术的缺点", bold=True, size=24)
    add("（1）查询结果孤立。现有统计平台通常以单次查询覆盖前次结果，难以在同一界面中同时保留多个查询结果，从而无法便捷实现相邻年份、相同分析类型或不同对象之间的对比分析。")
    add("（2）异构数据难以统一表达。教学成果奖数据包含图表型结果、表格型结果和词云图等多种表达形式，尤其是研究主题情况表存在层次、类别、内容、奖数和占比等多列关联关系，现有通用图表平台缺少专门的标准化处理逻辑。")
    add("（3）问答与当前查询脱节。通用大模型问答系统难以识别用户提问所指向的具体查询对象，容易将“研究主题分布”误解为“地理位置分布”，或者在有多张查询结果并行存在时无法绑定最近结果。")
    add("（4）问答范围过窄或过宽。若仅依据静态数据摘要回答，则系统只能复述统计描述，无法完成标题推荐、选题建议等需要模型综合推理的问题；若完全依赖模型自由回答，则又容易丢失数据依据。")
    add("（5）交互链路不完整。现有方案通常没有将查询、对比、问答、下载导出和流式展示有机整合，导致用户在分析过程中仍需借助其他软件进行二次整理。")

    add("四、本专利申请所解决的技术问题", bold=True, size=24)
    add("本专利申请旨在解决以下技术问题：")
    add("（1）如何将历届教学成果奖中来源不同、结构不同、维度不同的数据进行统一建模、标准化存储和规范化输出，使其能够被同一套前后端系统稳定调用。")
    add("（2）如何构建一种支持多查询卡片并行存在的可视化检索工作台，使用户能够同时保留多个年份和多个维度的分析结果，并在满足条件时自动生成同类型对比结果。")
    add("（3）如何针对教学成果奖中的图表型、表格型和词云型结果建立不同的数据摘要机制，使后续智能问答能够准确理解当前数据内容，而非仅依赖页面标题或模糊历史消息。")
    add("（4）如何构建一种上下文感知的大模型问答路由机制，使系统既能够对明确依赖当前查询数据的问题进行基于证据的回答，也能够对标题推荐、趋势判断、热点归纳等问题，在结合当前数据线索的基础上调用大模型自身推理能力完成回答。")
    add("（5）如何以统一交互流程实现查询、对比、智能问答、流式输出及结果导出，从而降低教学成果奖分析的使用门槛，提高数据利用效率和辅助决策能力。")

    add("五、本专利申请技术方案的详细阐述（发明内容，重点介绍）", bold=True, size=24)
    add("1、本专利申请的总体技术方案附图，包括流程图、硬件连接示意图等", bold=True, size=24)
    add("图2  本发明系统总体架构图。该系统至少包括前端交互层、分析服务层、数据存储层和大模型问答服务层。前端交互层接收用户查询条件和问答请求；分析服务层负责生成图表数据、表格数据、词云数据和对比结果；数据存储层保存教学成果奖结构化数据；大模型问答服务层根据查询上下文和会话状态生成文字结论。")
    add("【插图位置：图2 本发明系统总体架构图】")
    add("结合上述附图，本专利申请总体技术方案的实现过程如下：用户首先在前端页面中创建至少一个查询卡片，并在每张查询卡片中输入年份和分析类型；前端将查询条件发送至后端分析服务；后端根据查询类型调用对应的数据适配逻辑，从MySQL数据库中提取目标数据，并将结果规范化为图表、表格或词云数据结构；前端展示每张查询卡片的结果，并允许用户对相邻且同类型的结果发起对比；系统在每次查询完成后自动构建查询上下文摘要，并在用户进行智能问答时将该摘要作为上下文输入；后端根据问题类型选择数据型问答模式或上下文泛化问答模式，调用大模型服务并以流式方式返回结果；最后，系统支持将图表、表格等结果导出，形成完整的数据分析闭环。")

    add("2.1 教学成果奖数据统一建模与标准化管理模块", bold=True, size=24)
    add("本专利首先建立面向教学成果奖分析的统一数据模型。该模型至少包含年份、成果名称、地域信息、学科类型、学校层次、研究主题层次、研究主题类别、研究主题内容、奖数、占比、成果完成模式、完成人员合作情况等字段。对不同来源的数据表，系统通过字段映射、命名归一化、空值处理、百分比标准化和主题项规范化等手段完成预处理，并写入统一的MySQL数据库中。")
    add("对于研究主题情况表这类层次化数据，本专利针对“层次—类别—内容—奖数—占比(%)”之间的关联关系，设计了专门的标准化逻辑。该逻辑能够识别小计、合计等汇总项，规范不同年份中同义字段和不同粒度字段的写法，并在前端展示与导出时恢复为清晰统一的表格结构。")

    add("2.2 多维可视化检索工作台模块", bold=True, size=24)
    add("本专利在前端构建多查询卡片并行的工作台界面。每张查询卡片均为独立的分析任务单元，用户可针对任意卡片设置年份和分析类型。分析类型至少包括地理位置分布、学科类型分布、学校层次分布、研究主题情况表、获奖成果完成模式情况、完成人员合作情况表以及研究主题词云图。")
    add("用户发起查询后，后端根据分析类型调用不同的处理链路：对于图表型结果，将数据库结果统一转换为标签数组和数据数组；对于表格型结果，将数据库结果统一转换为列结构和行结构；对于词云型结果，则调用预生成或实时生成的词云资源。前端再根据结果类型自动选择柱状图、饼图、表格或词云图进行展示，从而使同一系统可以承载多种成果奖分析视图。")
    add("图3  多维可视化检索工作台界面示意图")
    add("【插图位置：图3 多维可视化检索工作台界面示意图】")

    add("2.3 同类型结果自动对比分析模块", bold=True, size=24)
    add("本专利进一步设计同类型结果自动对比机制。当两张相邻查询卡片均已生成结果且分析类型一致时，系统允许用户触发对比操作。后端对两次结果的类别标签进行并集对齐，并将缺失类别补零，从而生成统一的对比数据集。前端再基于该统一数据集绘制对比图表，用于展示不同年份或不同对象之间的结构差异。")
    add("对于词云型结果，对比模块采用双词云并排展示方式；对于图表型结果，对比模块采用统一对比柱状图方式。通过这种方式，系统能够在不改变原始查询卡片内容的前提下，生成独立的对比结果区域，并自动滚动到该区域，增强连续分析体验。")

    add("2.4 查询上下文摘要构建模块", bold=True, size=24)
    add("在每次查询成功后，本专利不只保存原始数据结果，还自动构建结构化查询上下文摘要。该摘要至少包括查询年份、查询类型、结果标题、主要类别、对应计数、占比、热点项目、表格行数、查询时间戳等信息。对于图表型结果，系统提取占比最高的若干类别和统计值；对于研究主题情况表，系统提取热点研究主题、所属层次、所属类别及其奖数占比；对于词云型结果，系统记录词云对应年份和主题分布语义。")
    add("每个查询卡片均绑定最近一次查询时间，系统可据此判断用户当前最可能指向的结果上下文。当用户问题中出现“刚刚查询的”“这张表”“上述结果”“当前主题”等代词时，后端优先将问题与最近查询的上下文进行绑定，以避免问答误指向其他卡片或历史数据。")

    add("2.5 融合可视化检索与大模型智能问答的路由模块", bold=True, size=24)
    add("本专利的智能问答模块并非单纯将用户问题直接提交给大模型，而是先经过问答路由处理。后端根据用户问题内容、查询上下文摘要以及历史会话消息，判断问题属于数据型问题、解释型问题还是泛化型问题。")
    add("其中，数据型问题是指直接围绕当前查询结果展开的问题，例如“2021年地理位置分布有什么特点”“学科类型中占比最高的是哪一类”；对于该类问题，系统将结构化摘要作为主要证据输入大模型，并要求模型给出结论和依据。")
    add("解释型问题是指需要结合当前数据进行趋势解释或差异说明的问题，例如“2021年和2025年的地区分布差异说明了什么”；对于该类问题，系统同时注入两个或多个查询上下文摘要，并指导模型从差异、结构和趋势角度进行归纳。")
    add("泛化型问题是指虽然与教学成果奖场景相关，但不完全受限于当前摘要的信息，例如“结合当前热门研究主题推荐申报标题”“根据这些主题建议后续选题方向”。对于该类问题，本专利将当前查询上下文中的热点主题词、层次信息和类别信息提供给大模型，同时允许模型在该数据线索基础上进行扩展推理，避免系统回答只停留在机械复述数据摘要的层面。")

    add("2.6 多轮会话、流式输出与导出模块", bold=True, size=24)
    add("为增强交互连续性，本专利为每次问答会话生成会话标识，并在后端维护对应的历史消息与上下文记录，从而支持多轮对话。系统在问答时以流式方式返回模型输出，前端逐段渲染文本并自动滚动到底部，使用户可以像使用主流大模型产品一样实时观察回答生成过程。")
    add("在结果导出方面，本专利支持图表下载为PNG格式、普通表格下载为CSV格式、研究主题情况表下载为带编码兼容和格式优化的表格文件。由此，用户既可以进行在线分析，也可以将中间结果导出用于汇报、归档或进一步编辑。")

    add("3、本专利申请的具体实施例", bold=True, size=24)
    add("3.1 具体实施例1", bold=True, size=24)
    add("（1）实施例1的流程图或系统图")
    add("图4  以2021年和2025年地理位置分布对比分析为例的系统流程图")
    add("【插图位置：图4 以2021年和2025年地理位置分布对比分析为例的系统流程图】")
    add("（2）结合上述附图，描述实施例1技术方案详细的实现过程。")
    add("1 运行环境")
    add("本实施例运行在Windows 11或Ubuntu 22.04平台，后端采用Python 3.x与Flask框架实现，前端采用Vue 3与Vite实现，可视化绘制采用Chart.js，数据存储采用MySQL 8.0，大模型服务采用具备对话生成能力的商用或开源大语言模型接口。浏览器环境可为Chrome、Edge等现代浏览器。")
    add("2 数据来源介绍")
    add("本实施例以浙江省高等教育教学成果奖的历届结构化数据为基础，至少包含2021年和2025年两个年份的成果奖信息。数据中包含成果的地域信息、学科类型、学校层次、合作情况、研究主题及相关统计字段。")
    add("3 系统使用过程")
    add("3.1 查询过程")
    add("用户在第一张查询卡片中选择2021年和“地理位置分布”，在第二张查询卡片中选择2025年和“地理位置分布”，系统分别向后端发送查询请求。后端调用相同的统计模板对两年数据进行聚合，返回城市标签及对应奖数，并在前端分别渲染为图表。系统同时对两张卡片分别生成查询上下文摘要，例如各年份占比最高城市、前二或前三城市奖数及占比信息。")
    add("3.2 对比过程")
    add("用户点击两张相邻查询卡片之间的“对比”按钮后，系统判断两张卡片分析类型一致，从而启动同类型对比链路。后端将2021年和2025年的城市类别取并集，对不存在于某一年的城市自动补零，再生成统一的对比图表数据。前端在独立的“对比结果”区域展示结构化对比图。")
    add("3.3 问答过程")
    add("用户在智能问答区域输入“2021年和2025年地理位置分布有什么差异”。前端将该问题及最近的查询上下文摘要一并发送到后端。后端识别到该问题属于解释型问题，自动绑定两张最近的地理位置分布结果，并将两份上下文摘要组织为提示信息输入大模型。大模型返回基于统计结果的差异说明，后端再以流式方式将答案返回到前端显示。")
    add("4 系统输出")
    add("本实施例的输出至少包括：2021年地理位置分布图、2025年地理位置分布图、两年对比结果图以及基于数据摘要生成的自然语言差异分析结论。用户还可将图表导出为PNG文件以供汇报使用。")

    add("3.2 具体实施例2", bold=True, size=24)
    add("（1）实施例2的流程图或系统图")
    add("图5  以研究主题情况表联动大模型生成标题建议为例的系统流程图")
    add("【插图位置：图5 以研究主题情况表联动大模型生成标题建议为例的系统流程图】")
    add("（2）结合上述附图，描述实施例2技术方案详细的实现过程。")
    add("1 运行环境")
    add("本实施例与实施例1采用相同的前后端运行环境和数据库环境。")
    add("2 数据来源介绍")
    add("本实施例重点使用研究主题情况表数据。该数据按“层次—类别—内容—奖数—占比(%)”进行组织，其中包含战略性、战术性等不同层次下的各类研究主题内容及对应奖数。")
    add("3 系统使用过程")
    add("3.1 研究主题表查询")
    add("用户在查询卡片中选择某一年份，例如2025年，并选择“研究主题情况表”。后端从数据库中获取对应记录后，对层次字段、类别字段和内容字段进行规范化处理，识别并保留小计、合计结构，随后以专门设计的表格视图展示。与此同时，系统从该表中自动提取热点主题内容及其奖数占比，构建查询上下文摘要。")
    add("3.2 智能问答与标题生成")
    add("用户进一步在智能问答区域输入“结合这些热门研究主题推荐5个申报标题”。前端将该问题与最新的研究主题情况表上下文一并提交。后端识别该问题不属于单纯的数据复述，而属于泛化型问题，因此启动上下文泛化问答模式：一方面将研究主题表中的热点主题、类别与层次信息作为数据依据输入大模型，另一方面允许模型基于教学成果奖申报场景进行扩展推理，最终生成若干与主题热点相匹配的标题建议。")
    add("3.3 结果导出")
    add("用户可将研究主题情况表导出为兼容办公软件的表格文件，用于后续编辑与整理。导出文件中保留“层次、类别、内容、奖数、占比(%)”等核心列，避免内部辅助字段暴露给最终用户。")
    add("4 系统输出")
    add("本实施例的输出至少包括：规范化研究主题情况表、围绕该表构建的上下文摘要，以及结合数据热点和模型推理生成的标题建议文本。")

    add("六、本专利申请的技术效果", bold=True, size=24)
    add("1、本专利将教学成果奖多源异构数据统一建模并标准化处理，使地域、学科、学校层次、研究主题、合作情况等多个维度能够通过同一平台进行稳定查询和展示。")
    add("2、本专利通过多查询卡片并行工作台保留多个分析视角，显著降低了用户在多个年份、多种维度之间来回切换的成本。")
    add("3、本专利通过同类型对比机制，实现不同年份或不同对象分析结果的自动对齐与自动对比，提高了结构差异识别效率。")
    add("4、本专利通过查询上下文摘要构建和最近结果优先绑定机制，有效降低了大模型问答中出现答非所问、上下文指代错误的概率。")
    add("5、本专利通过数据型问答与泛化型问答的路由控制，使系统既能够提供基于证据的数据结论，又能够完成标题推荐、主题归纳、趋势判断等更高层次的辅助分析。")
    add("6、本专利通过流式问答输出和结果导出机制，提升了交互体验和成果复用能力，使教学成果奖分析从静态报表阅读转向可交互、可追问、可导出的智能分析流程。")

    add("七、本专利申请的关键点和欲保护点是什么？", bold=True, size=24)
    add("1、面向教学成果奖数据的统一数据模型及其标准化处理方法。")
    add("2、基于多查询卡片的可视化检索工作台及同类型结果自动对比机制。")
    add("3、面向图表、表格和词云等不同结果形态的查询上下文摘要构建方法。")
    add("4、基于最近查询结果绑定、上下文感知和问题类型识别的大模型智能问答路由方法。")
    add("5、将可视化检索、对比分析、智能问答、流式输出和结果导出集成为一体的教学成果奖数据分析系统。")

    add("八、针对第五条所阐述的技术方案，是否还有别的替代方案同样能完成发明目的", bold=True, size=24)
    add("有。为扩大保护范围，本专利申请的替代方案至少包括：")
    add("（1）数据库可由MySQL替换为PostgreSQL、MariaDB或其他关系数据库；")
    add("（2）前端框架可由Vue替换为React或其他支持组件化交互的前端框架；")
    add("（3）图表引擎可由Chart.js替换为ECharts或其他图形渲染库；")
    add("（4）大模型服务可由不同商业模型或开源模型替换，只要其能够接收查询上下文摘要并返回自然语言答案；")
    add("（5）会话上下文可存储在内存、Redis或数据库中，只要能够支持多轮问答和最近查询上下文绑定；")
    add("（6）研究主题情况表导出格式可采用CSV、XML电子表格或其他可编辑办公文档格式。")

    add("九、其他有助于专利管理人员理解本技术的资料", bold=True, size=24)
    add("1、浙江省高等教育教学成果奖历届公开数据样表。")
    add("2、系统前端界面原型图、查询卡片界面示意图、对比结果界面示意图。")
    add("3、后端接口说明文档，包括可视化查询接口、研究主题情况表接口、词云接口、智能问答接口。")
    add("4、若需要，可补充大模型提示词组织逻辑、查询上下文摘要字段说明和系统部署拓扑图。")

    return paras


def main() -> None:
    paragraphs = build_paragraphs()
    document_xml = build_document_xml(paragraphs)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(OUTPUT_PATH, "w", ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", build_content_types_xml())
        zf.writestr("_rels/.rels", build_root_rels_xml())
        zf.writestr("docProps/core.xml", build_core_xml())
        zf.writestr("docProps/app.xml", build_app_xml())
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/styles.xml", build_styles_xml())
        zf.writestr("word/_rels/document.xml.rels", build_document_rels_xml())

    print(str(OUTPUT_PATH))


if __name__ == "__main__":
    main()
