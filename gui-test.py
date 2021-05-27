import PySimpleGUI as sg

sg.theme('LightGrey1')

col2 = sg.Column([[sg.Frame('Device BLE Data:', [[sg.Column([ 
                                                      [sg.Text('             Time                           pH     Temp (*C)      Battery (mV)       pH (mV)')],
                                                      [sg.Multiline(key='-DATATABLE-',size=(68,27), auto_refresh=True, disabled=True)]],size=(500,480))]])]],pad=(0,0))

col1 = sg.Column([
    # Categories sg.Frame
    [sg.Frame('BLE Status:', [[sg.Text('CONNECTED', text_color='green')]])],
    # Information sg.Frame
    [sg.Frame('Calibration Points:', 
                            [[sg.Text(), sg.Column([
                                     [sg.Text('Point 1, pH 10:', font='Ubuntu 13')],
                                     [sg.Multiline(key='-PT1-', size=(19,1), auto_refresh=True, disabled=True),
                                      sg.Button('Read Data', key='-PT1READ-')],
                                     [sg.Text('Point 2, pH 7:', font='Ubuntu 13')],
                                     [sg.Multiline(key='-PT2-', size=(19,1), auto_refresh=True, disabled=True),
                                      sg.Button('Read Data', key='-PT2READ-')],
                                     [sg.Text('Point 3, pH 4:', font='Ubuntu 13')],
                                     [sg.Multiline(key='-PT3-', size=(19,1), auto_refresh=True, disabled=True),
                                      sg.Button('Read Data', key='-PT3READ-')],
                                     [sg.Text('Calibration Instructions:')],
                                     [sg.Multiline(key='-INS-', size=(45,11), auto_refresh=True, disabled=True)],
                                     [sg.Button('Continue', key='-CONTINUE-', pad=(255,0))],
                             ], size=(380,450), pad=(0,0))]])], ], pad=(0,0))

col3 = sg.Column([[sg.Frame('Actions:',
                            [[sg.Column([[sg.Button(' EXIT ', pad=(40,0), button_color='OrangeRed'), sg.Button('RESTART')]],
                                        size=(290,45), pad=(0,0))]]),
                   sg.Frame('Calibration Results:',
                            [[sg.Column([[sg.Text('Sensitivity (mV / pH) :  ', font='Ubuntu 11'), sg.Text('          '), sg.Text('R^2 :  ', font='Ubuntu 11'), 
                                          sg.Text('               '), sg.Text('Offset (mV):  ', font='Ubuntu 11'), sg.Text('           ')]], size=(550,45), pad=(30,0))]], pad=(10,0))]])

# The final layout is a simple one
layout = [[col1, col2],
          [col3]]

# A perhaps better layout would have been to use the vtop layout helpful function.
# This would allow the col2 column to have a different height and still be top aligned
# layout = [sg.vtop([col1, col2]),
#           [col3]]


window = sg.Window('Lura Health Calibration Tool', layout, resizable=True)

while True:
    event, values = window.read()
    if event == sg.WIN_CLOSED or event == ' EXIT ':
        break

window.close()
