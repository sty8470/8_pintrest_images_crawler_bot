# -*- conding: utf-8 -*-
'''
개요: 유저가 원하는 키워드의 이미지들을 Pintrest 웹사이트에서 추출하는 봇

실행방식: 유저가 검색을 원하는 핵심 member_id와 pageNum를 입력받는다.

[Workflow]
1. 유저에게 입력받은 member_id와 pageNum을 기준으로 openAPI request을 보낸다.
2. 정상적인 응답이 돌아오면, 핵심 데이터들을 정해진 디렉토리 안에 저장한다.
3. SQL에도 같이 저장한다.

'''
import csv
import logging
import time
import traceback
import sys
import os
import random
import requests

from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5 import uic

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium import webdriver 

os.makedirs('./결과물', exist_ok=True)
os.makedirs('./상태로그', exist_ok=True)

download_folder = os.path.join(os.getcwd(), "결과물")

# 상태로그 파일이름 설정을 INFO 레벨로 지정하고 -> 로깅 파일 이름과 로깅 파일 형식을 지정한다.
logging.basicConfig(filename=f'상태로그/{datetime.today().strftime("%Y-%m-%d")}.log', level=logging.INFO, format='[%(asctime)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

ui_layout_class = uic.loadUiType("pintrest_crawler.ui")[0]

class WindowClass(QMainWindow, ui_layout_class):
    def __init__(self):
        # QMainWindow의 생성자를 호출하고, ui_layout_class의 UI 구성요소를 세팅합니다.
        super().__init__()
        self.setupUi(self)
        # 각 버튼들이 클릭되었을 때, 해당하는 메소드가 호출되도록 연결합니다.
        self.executeButton.clicked.connect(self.execute)
        self.stopButton.clicked.connect(self.stop)
        self.directButton.clicked.connect(self.direct)
        self.registerButton.clicked.connect(self.register)
        self.saveButton.clicked.connect(self.search)
        # 1초마다 start_working_thread의 함수를 호출하는 QTimer 객체를 생성합니다.
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.start_working_thread)
        
        self.member_id = None
        self.password = None
        self.searchword = None
        self.scrollNum = None
        
        self.id = None 
        self.pw = None
    
    def search(self):
        self.searchword = self.keyword_line_edit.text().strip()
        self.scrollNum = self.scroll_line_edit.text().strip()
        
        if not self.scrollNum.isnumeric():
            msg = QMessageBox()
            msg.setWindowTitle("알림")
            msg.setText('키워드 및 스크롤 횟수 등록실패')
            msg.setIcon(QMessageBox.Warning)
            msg.exec_()
            return
        
        msg = QMessageBox()
        msg.setWindowTitle("알림")
        msg.setText('키워드 및 스크롤 횟수 등록성공')
        msg.setIcon(QMessageBox.Information)
        msg.exec_()
        
        self.keyword_line_edit.setEnabled(False)
        self.scroll_line_edit.setEnabled(False)
    
    def execute(self):
        '''
        동작을 실행하기 전에 필요한 조건을 검사하고, 조건에 따라 알림 메시지를 표시하고 해당 동작을 실행하는 등의 작업을 수행합니다.
        '''
        if self.statusSignal.styleSheet() == 'color:green': 
            return

        if self.validated == False:
            msg = QMessageBox()
            msg.setWindowTitle("알림")
            msg.setText('아이디와 비밀번호 작성 필요')
            msg.setIcon(QMessageBox.Information)
            msg.exec_()
            return

        self.task_type = "동작"
        self.set_stylesheet("대기중")
        self.executeButton.setEnabled(False)
        self.stopButton.setEnabled(True)
        self.directButton.setEnabled(False)

        self.timer.start()

    def register(self):
        '''
        함수는 사용자가 제출한 로그인 정보를 서버에 전송하여 로그인을 시도하고, 
        응답에 따라 로그인 성공 또는 실패를 처리합니다. 로그인 성공 시 사용자 정보를 저장하고 필드를 비활성화하는 등의 작업을 수행합니다.
        '''

        self.member_id = self.member_id_line_edit.text()
        self.password = self.password_line_edit.text()

        self.member_id_line_edit.clear()
        self.password_line_edit.clear()

        self.member_id_line_edit.setDisabled(True)
        self.password_line_edit.setDisabled(True)
        self.stopButton.setDisabled(True)

        if self.member_id.replace(' ','').strip() == self.id and self.password.replace(' ','').strip() == self.pw and len(self.member_id) > 0 and len(self.password) > 0:
            self.validated = True
            msg = QMessageBox()
            msg.setWindowTitle("알림")
            msg.setText('로그인 성공')
            self.registerButton.setDisabled(True)
            msg.setIcon(QMessageBox.Information)
            msg.exec_()
        else:
            msg = QMessageBox()
            msg.setWindowTitle("알림")
            msg.setText('로그인 실패')
            msg.setIcon(QMessageBox.Information)
            msg.exec_()

    def direct(self):
        if self.statusSignal.styleSheet() == 'color:blue': 
            return
        
        if not all([self.member_id, self.password, self.searchword, self.scrollNum]):
            msg = QMessageBox()
            msg.setWindowTitle("알림")
            msg.setText('즉시실행 실패')
            msg.setIcon(QMessageBox.Warning)
            msg.exec_()
            return
        
        self.task_type = "즉시실행"
        self.set_stylesheet("대기중")
        self.executeButton.setEnabled(False)
        self.directButton.setEnabled(False)

        self.main_thread = PintrestCrawler(self,self.member_id,self.password, self.searchword, self.scrollNum)
        self.main_thread.log.connect(self.set_log)
        self.main_thread.finished.connect(self.working_finished)
        self.main_thread.run()

        self.set_log('Started!')
    
    def stop(self):
        self.set_stylesheet("미동작")
        self.timer.stop()
        self.executeButton.setEnabled(True)
        self.stopButton.setEnabled(False)
        self.directButton.setEnabled(True)

    def working_finished(self):
        # 객체의 실행이 완료될 때 까지 기다립니다.
        self.main_thread.wait()
        # 이 메서드는 객체의 소유권을 Qt 이벤트 루프에게 양도하고, 안전하게 객체를 삭제하기 위해 이벤트 큐에 삭제 이벤트를 추가합니다.
        self.main_thread.deleteLater()
        # self.main_thread 변수를 삭제합니다. 이렇게 하면 메모리에서 해당 객체에 대한 참조가 제거됩니다.
        del self.main_thread

        if self.task_type == "동작":
            self.set_stylesheet("대기중")
        elif self.task_type == "즉시실행":
            self.set_stylesheet("미동작")
            self.executeButton.setEnabled(True)
            self.directButton.setEnabled(True)

    def set_stylesheet(self,flag):
        '''
        UserRewardsBot 클래스의 작업읭 성격에 따라서, 상태색깔과 상태메세지를 업데이트 합니다.
        '''
        if flag == "대기중": 
            self.statusSignal.setStyleSheet('color:green')
            self.boardLabel.setText("대기중")
        elif flag == "동작중": 
            self.statusSignal.setStyleSheet('color:blue')
            self.boardLabel.setText("동작중")
        elif flag == "미동작": 
            self.statusSignal.setStyleSheet('color:red')
            self.boardLabel.setText("미동작")

    def start_working_thread(self):
        '''
        UserRewardsBot 클래스의 작업이 시작될 때 동작하는 구간
        '''
        # 현재 시간을 할당하기
        time = QTime.currentTime()
        # time_arr 메소드를 호출합니다 -> 현재 self.arr 리스트에 추가되어 있는 "Hour" 체크하기
        self.time_arr()
        # self.arr에 추가되어있는 정각시간이 되면,
        if time.toString('mm.ss') == '00.00' and time.toString('hh') in self.arr:
            # main_thread을 호출하여서 당시의 INFO 로그를 남기고 쓰레드 실행/종료를 시작합니다.
            self.main_thread = PintrestCrawler(self,self.member_id,self.password)
            self.main_thread.log.connect(self.set_log)
            self.main_thread.finished.connect(self.working_finished)
            self.main_thread.start()
            self.set_log('Started!')

    def time_arr(self):
        '''
        이 함수가 호출되면, 00시부터 23시까지 해당 시간(시간문자열)을 self.arr 리스트에 추가합니다.
        이는 배치성 작업으로 인해서 1시간 마다 self.arr 리스트에 추가된 시간에 해당 봇이 동작하기 위해서 관리하기 위함입니다.
        '''
        self.arr = []
        if self.time00Hour.isChecked(): self.arr.append('00')
        if self.time01Hour.isChecked(): self.arr.append('01')
        if self.time02Hour.isChecked(): self.arr.append('02')
        if self.time03Hour.isChecked(): self.arr.append('03')
        if self.time04Hour.isChecked(): self.arr.append('04')
        if self.time05Hour.isChecked(): self.arr.append('05')
        if self.time06Hour.isChecked(): self.arr.append('06')
        if self.time07Hour.isChecked(): self.arr.append('07')
        if self.time08Hour.isChecked(): self.arr.append('08')
        if self.time09Hour.isChecked(): self.arr.append('09')
        if self.time10Hour.isChecked(): self.arr.append('10')
        if self.time11Hour.isChecked(): self.arr.append('11')
        if self.time12Hour.isChecked(): self.arr.append('12')
        if self.time13Hour.isChecked(): self.arr.append('13')
        if self.time14Hour.isChecked(): self.arr.append('14')
        if self.time15Hour.isChecked(): self.arr.append('15')
        if self.time16Hour.isChecked(): self.arr.append('16')
        if self.time17Hour.isChecked(): self.arr.append('17')
        if self.time18Hour.isChecked(): self.arr.append('18')
        if self.time19Hour.isChecked(): self.arr.append('19')
        if self.time20Hour.isChecked(): self.arr.append('20')
        if self.time21Hour.isChecked(): self.arr.append('21')
        if self.time22Hour.isChecked(): self.arr.append('22')
        if self.time23Hour.isChecked(): self.arr.append('23')

    def set_log(self,data):
        '''
        ListWidget에 실행시 로그를 남겨서 업데이트 하며, 이 정보는 "상태로그" 밑에 저장됩니다.
        '''
        self.listWidget.insertItem(0,f"{datetime.today().strftime('[%Y-%m-%d %H:%M:%S]')} {str(data)}")
        logging.info(str(data))
        

class PintrestCrawler(QThread):
    log = pyqtSignal(str)

    def __init__(self, parent, member_id, password, searchword, scrollnum):
        super().__init__(parent)
        self.member_id = member_id
        self.password = password
        self.searchword = searchword
        self.scroll_num = scrollnum
        self.driver = None
        
    def login_to_pintrest(self):
        url = "https://www.pinterest.co.kr/login/"
        # chrome_driver_path = "chromedriver.exe"  # Chrome WebDriver의 경로를 적절하게 수정하세요.

        # Chrome WebDriver를 명시적으로 실행하고 경로를 지정합니다.
        # self.driver = webdriver.Chrome(executable_path=chrome_driver_path, options=webdriver.ChromeOptions())
        
        service = Service(executable_path='chromedriver.exe')
        options = webdriver.ChromeOptions()
        self.driver = webdriver.Chrome(service=service, options=options)
        
        # 해당 웹사이트를 오픈합니다.
        self.driver.get(url=url)
        time.sleep(3)
        self.driver.find_element(By.ID, "email").send_keys("") ### EDIT
        self.driver.find_element(By.ID, "password").send_keys("") ### EDIT
        self.driver.find_element(By.XPATH, '//*[@id="mweb-unauth-container"]/div/div[3]/div/div/div[3]/form/div[7]/button/div').click()
        time.sleep(5)
        
    def load_searching_result(self):
        """  
        Pintrest의 메인 화면을 30번 정도 스크롤 다운하기
        """
        # 키워드 칸을 찾아서, 원하는 키워드를 검색합니다.
        # search_keyword = "inspirational image"
        search_box = self.driver.find_element(By.XPATH, '//*[@id="searchBoxContainer"]/div/div/div[2]/input')
        search_box.send_keys(self.searchword)
        time.sleep(1)
        search_box.send_keys(Keys.ENTER)
        time.sleep(3)
        self.driver.maximize_window()
        time.sleep(1)
        
        # 총 10번 정도 스크롤을 내립니다.
        self.all_urls = list(set(self.scroll_down_body_page(self.scroll_num)))
        
        # CSV 파일에 결과를 저장합니다.
        self.save_img_urls_to_csv()
        
        
    # n번만큼 스크롤을 내립니다.
    def scroll_down_body_page(self, n):
        imgs = []
        self.body_element = self.driver.find_element(By.TAG_NAME, 'body')
        time.sleep(1)
        for i in range(int(n)):
            self.body_element.send_keys(Keys.PAGE_DOWN)
            time.sleep(3)
            self.set_random_time_out()
            # 이미지 태그 찾기
            image_elements = self.driver.find_elements(By.XPATH, '//img[@src]')
            # 이미지의 src 속성 가져오기
            image_urls = [element.get_attribute('srcset') for element in image_elements]
            imgs.extend(image_urls)
        
        return imgs

    # 랜덤한 시간만큼 시간을 멈추게 하기
    def set_random_time_out(self):
        return time.sleep(random.uniform(0.3, 0.7))
            
    def save_img_urls_to_csv(self):
        try:
            # CSV 파일로 내보낼 파일 이름
            csv_file_name = "image_urls.csv"

            # CSV 파일 열기 및 데이터 쓰기
            with open(csv_file_name, mode='w', newline='') as csv_file:
                csv_writer = csv.writer(csv_file)

                # CSV 파일의 첫 번째 행에 열 이름 쓰기 (선택 사항)
                csv_writer.writerow(["Image URL"])

                # 이미지 URL을 CSV 파일에 쓰기
                for url in self.all_urls:          ### EDIT 아래와 같은 형식이 되어야 한다.
                    '''
                    image_urls = [
                        "https://i.pinimg.com/236x/9c/f1/7f/9cf17fd9b82ab0de67f226b9a06a65c6.jpg",
                        "https://i.pinimg.com/236x/cf/a4/3a/cfa43a9d0fc0adee88ac941ce6a6362a.jpg",
                        "https://i.pinimg.com/236x/10/ad/cf/10adcfdc64e44b2fcbe5868155de84b9.jpg",
                        "https://i.pinimg.com/236x/d7/63/d2/d763d27e03ee8e3fb859a79c3ebb9e81.jpg"
                    ]
                    '''
                    csv_writer.writerow([url])

            self.log.emit(f"이미지 URL이 {csv_file_name} 파일로 내보내졌습니다.")
            print(f"이미지 URL이 {csv_file_name} 파일로 내보내졌습니다.")
        except Exception as e:
            error_message = f"CSV 파일 저장 중 오류 발생: {str(e)}"
            logging.error(error_message)
            logging.info(error_message)
            self.log.emit(error_message)
    
    def convert_img_to_jpg(self):
        # 이미지를 저장할 폴더 생성
        if not os.path.exists('downloaded_images'):
            os.makedirs('downloaded_images')

        # 이미지 다운로드 및 저장
        for index, image_url in enumerate(self.all_urls, start=1):
            response = requests.get(image_url)
            if response.status_code == 200:
                # 이미지를 바이너리 모드로 저장
                with open(f'downloaded_images/image{index}.jpg', 'wb') as f:
                    f.write(response.content)
                msg = f'이미지 {index} 다운로드 및 저장 완료'
                self.log.emit(msg)
                print(msg)
            else:
                msg = f'이미지 {index} 다운로드 실패'
                self.log.emit(msg)
                print(msg)

        msg = '모든 이미지 다운로드 및 저장 완료'
        self.log.emit(msg)
        print(msg)

    # 주요 함수의 실행부분     
    def run(self):
        try:
            self.login_to_pintrest()
            self.load_searching_result()
            self.convert_img_to_jpg()
        
        except:
            error = traceback.format_exc()
            logging.error(error)
            logging.info(error)
            self.log.emit(error)
        
        
if __name__ == "__main__" :

    app = QApplication(sys.argv) 
    myWindow = WindowClass() 
    myWindow.show()
    app.exec_()