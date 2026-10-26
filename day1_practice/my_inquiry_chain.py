# 코드 리뷰 요청 접수
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_aws import ChatBedrockConverse
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.runnables import RunnableParallel

load_dotenv()
llm = ChatBedrockConverse(
    model="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    region_name="us-east-1",
    temperature=0,
)

# --- 부품 A: 리뷰 요청 분류 ---
class ReviewRequest(BaseModel):
    change_type: str = Field(description="변경 유형: '버그수정', '신규기능', '핫픽스' 중 하나")
    risk: str = Field(description="위험도: '높음', '보통', '낮음' 중 하나")
    summary: str = Field(description="요청 내용 한 줄 요약")

routing_parser = JsonOutputParser(pydantic_object=ReviewRequest)
routing_prompt = PromptTemplate(
    template="다음 코드 리뷰 요청을 분류해줘.\n\n요청: {request}\n\n{format_instructions}",
    input_variables=["request"],
    partial_variables={"format_instructions": routing_parser.get_format_instructions()},
)
routing_chain = routing_prompt | llm | routing_parser

# --- 부품 B: 답변 초안 ---
answer_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "너는 코드 리뷰 담당자야. 존댓말로 세 문장으로 답해줘. "
     "접수 확인, 언제 리뷰할지, 필요한 추가 정보를 한 문장씩 써줘."),
    ("human", "{request}"),
])
answer_chain = answer_prompt | llm | StrOutputParser()

# --- 두 체인 같이 실행 ---
full_chain = RunnableParallel(routing=routing_chain, draft=answer_chain)

# --- 테스트 ---
requests = [
    "로그인 화면에서 비밀번호 틀리면 에러 메시지 안 나오는 버그 고쳤습니다. 리뷰 부탁드려요.",
    "결제 API 오류 나서 급하게 수정했어요. 지금 운영에서 문제 생기고 있어요!",
    "이거 한번 봐주실 수 있나요?",  # 애매한 입력
]

for req in requests:
    result = full_chain.invoke({"request": req})
    print("요청:", req)
    print("변경 유형:", result["routing"]["change_type"])
    print("위험도:", result["routing"]["risk"])
    print("요약:", result["routing"]["summary"])
    print("답변 초안:", result["draft"])
    print("------------------------------------------------------------")
