"""
テスト用データセット生成

Day 2-3の実装テスト用に、小規模で管理可能な
テストデータセットを生成します。
"""

from typing import List
from dataclasses import dataclass


@dataclass
class MMUTestQuestion:
    """テスト用MMLU問題"""
    question: str
    choices: List[str]
    answer: str
    subject: str
    grade: str


@dataclass
class GSM8KTestProblem:
    """テスト用GSM8K問題"""
    problem: str
    solution: str
    answer: str
    problem_id: str


def generate_mmlu_test_data(num_samples: int = 20) -> List[MMUTestQuestion]:
    """
    テスト用MMLU問題を生成
    
    Args:
        num_samples: 生成する問題数
        
    Returns:
        MMUTestQuestion リスト
    """
    test_data = [
        # Abstract Algebra
        {
            "question": "What is the order of the group Z_6?",
            "choices": ["2", "3", "6", "12"],
            "answer": "C",
            "subject": "abstract_algebra",
            "grade": "college"
        },
        {
            "question": "Find the center of the group S_3.",
            "choices": ["S_3", "{e}", "{e, (123), (132)}", "{e, (12)}"],
            "answer": "B",
            "subject": "abstract_algebra",
            "grade": "college"
        },
        # Anatomy
        {
            "question": "Which bone is the longest in the human body?",
            "choices": ["Humerus", "Femur", "Tibia", "Fibula"],
            "answer": "B",
            "subject": "anatomy",
            "grade": "college"
        },
        {
            "question": "What is the primary function of mitochondria?",
            "choices": ["Protein synthesis", "ATP production", "DNA storage", "Photosynthesis"],
            "answer": "B",
            "subject": "anatomy",
            "grade": "college"
        },
        # High School Biology
        {
            "question": "What is the powerhouse of the cell?",
            "choices": ["Nucleus", "Mitochondria", "Ribosome", "Golgi apparatus"],
            "answer": "B",
            "subject": "high_school_biology",
            "grade": "high_school"
        },
        {
            "question": "Which process produces glucose from CO2 and water?",
            "choices": ["Respiration", "Photosynthesis", "Fermentation", "Decomposition"],
            "answer": "B",
            "subject": "high_school_biology",
            "grade": "high_school"
        },
        # High School Math
        {
            "question": "Solve for x: 2x + 5 = 13",
            "choices": ["2", "3", "4", "5"],
            "answer": "C",
            "subject": "high_school_mathematics",
            "grade": "high_school"
        },
        {
            "question": "What is the derivative of x^2?",
            "choices": ["x", "2x", "2", "x/2"],
            "answer": "B",
            "subject": "high_school_mathematics",
            "grade": "high_school"
        },
        # High School Physics
        {
            "question": "What is the SI unit of force?",
            "choices": ["Joule", "Newton", "Watt", "Pascal"],
            "answer": "B",
            "subject": "high_school_physics",
            "grade": "high_school"
        },
        {
            "question": "Which law states F = ma?",
            "choices": ["Newton's First Law", "Newton's Second Law", "Newton's Third Law", "Law of Inertia"],
            "answer": "B",
            "subject": "high_school_physics",
            "grade": "high_school"
        },
        # Adding more to reach num_samples
        {
            "question": "What is the capital of France?",
            "choices": ["London", "Paris", "Berlin", "Madrid"],
            "answer": "B",
            "subject": "geography",
            "grade": "high_school"
        },
        {
            "question": "In what year did World War II end?",
            "choices": ["1943", "1944", "1945", "1946"],
            "answer": "C",
            "subject": "history",
            "grade": "high_school"
        },
        {
            "question": "What is the chemical symbol for gold?",
            "choices": ["Go", "Gd", "Au", "Ag"],
            "answer": "C",
            "subject": "chemistry",
            "grade": "high_school"
        },
        {
            "question": "Which planet is known as the Red Planet?",
            "choices": ["Venus", "Mars", "Jupiter", "Saturn"],
            "answer": "B",
            "subject": "astronomy",
            "grade": "high_school"
        },
        {
            "question": "Who wrote 'Romeo and Juliet'?",
            "choices": ["Jane Austen", "Charles Dickens", "William Shakespeare", "Mark Twain"],
            "answer": "C",
            "subject": "literature",
            "grade": "high_school"
        },
    ]
    
    # 指定数に達するまでデータを複製
    questions = []
    for i in range(num_samples):
        data = test_data[i % len(test_data)]
        questions.append(MMUTestQuestion(
            question=data["question"],
            choices=data["choices"],
            answer=data["answer"],
            subject=data["subject"],
            grade=data["grade"]
        ))
    
    return questions


def generate_gsm8k_test_data(num_samples: int = 20) -> List[GSM8KTestProblem]:
    """
    テスト用GSM8K問題を生成
    
    Args:
        num_samples: 生成する問題数
        
    Returns:
        GSM8KTestProblem リスト
    """
    test_data = [
        {
            "problem": "Olivia has $23. She buys five bagels for $3 each. How much money does she have left?",
            "solution": "Five bagels cost 5 * $3 = $15.\nShe has $23 - $15 = $8 left.",
            "answer": "8"
        },
        {
            "problem": "Michael had 58 golf balls. On monday, he lost 23 golf balls. On tuesday, he lost 2 more. How many golf balls did he have at the end of tuesday?",
            "solution": "After Monday: 58 - 23 = 35 balls\nAfter Tuesday: 35 - 2 = 33 balls",
            "answer": "33"
        },
        {
            "problem": "There are 15 trees in the grove. Grove workers will plant trees in the grove today. After they are done there will be 21 trees. How many trees did the grove workers plant today?",
            "solution": "Trees planted = Final trees - Initial trees = 21 - 15 = 6",
            "answer": "6"
        },
        {
            "problem": "Shawn has five toys. For Christmas, he got two toys each from his mom and dad. How many toys does he have now?",
            "solution": "From mom: 2 toys\nFrom dad: 2 toys\nTotal new toys: 2 + 2 = 4\nTotal toys: 5 + 4 = 9",
            "answer": "9"
        },
        {
            "problem": "Jason had 20 lollipops. He gave Denny some lollipops. Now Jason has 12 lollipops. How many lollipops did Jason give to Denny?",
            "solution": "Lollipops given = Initial - Remaining = 20 - 12 = 8",
            "answer": "8"
        },
        {
            "problem": "If there are 3 cars in the parking lot and 2 more cars arrive, how many cars are in the parking lot?",
            "solution": "Cars in parking lot = 3 + 2 = 5",
            "answer": "5"
        },
        {
            "problem": "Leah had 32 chocolates and her sister had 42. If they ate 35, how many pieces do they have left in total?",
            "solution": "Total initially = 32 + 42 = 74\nRemaining = 74 - 35 = 39",
            "answer": "39"
        },
        {
            "problem": "If a book costs $12 and Jessica has $50, how much change will she get after buying the book?",
            "solution": "Change = Money she has - Cost of book = 50 - 12 = 38",
            "answer": "38"
        },
        {
            "problem": "A bakery made 200 cookies. They sold 145 cookies. How many cookies are left?",
            "solution": "Cookies left = Total made - Sold = 200 - 145 = 55",
            "answer": "55"
        },
        {
            "problem": "There are 5 red balls and 3 blue balls in a box. How many balls are there in total?",
            "solution": "Total balls = Red balls + Blue balls = 5 + 3 = 8",
            "answer": "8"
        },
    ]
    
    # 指定数に達するまでデータを複製
    problems = []
    for i in range(num_samples):
        data = test_data[i % len(test_data)]
        problems.append(GSM8KTestProblem(
            problem=data["problem"],
            solution=data["solution"],
            answer=data["answer"],
            problem_id=f"test_gsm8k_{i}"
        ))
    
    return problems


if __name__ == "__main__":
    # テストデータ生成デモ
    print("="*80)
    print("📚 テスト用データセット生成")
    print("="*80)
    
    print("\n[1] MMLU テストデータ:")
    mmlu_data = generate_mmlu_test_data(5)
    for i, q in enumerate(mmlu_data, 1):
        print(f"  Q{i}: {q.question}")
        print(f"      答え: {q.answer}")
    
    print("\n[2] GSM8K テストデータ:")
    gsm8k_data = generate_gsm8k_test_data(5)
    for i, p in enumerate(gsm8k_data, 1):
        print(f"  Q{i}: {p.problem}")
        print(f"      答え: {p.answer}")
    
    print("\n✅ テストデータ生成完了")
