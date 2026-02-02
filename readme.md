## 실행
```
pip install streamlit pandas plotly
streamlit run app.py
```

## git branch 만들어서 진행
1. 시작 전 메인 코드 가져오기: ``` git pull origin main ```
2. branch naming
   ``` feature-{추가하는 기능 이름} ```
3. ``` git checkout -b feature-{추가하는 기능 이름} ```
4. 이후 코드 수정/변경 진행

## 수정 후 git command
1. ``` git add . ```
2. ``` git commit -m "설명" ```
3. ``` git push origin feature-{추가하는 기능 이름} ```

## push 후 pr 전송
1. github 또는 vs code 에서 create pr
