from textbook_agent.cli import main

def test_status_without_api_or_pdf(tmp_path,capsys):
    assert main(['status','--output',str(tmp_path)])==0
    assert 'No saved runs' in capsys.readouterr().out

def test_missing_source_is_a_clear_preflight_error(tmp_path,capsys):
    result=main(['run','--pdf',str(tmp_path/'missing.pdf'),'--output',str(tmp_path),'--medium','en','--class','10','--subject','science','--edition','2024','--model','test'])
    assert result==1 and 'Source PDF' in capsys.readouterr().err
