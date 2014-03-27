import neuroml
import neuroml.writers as writers

import lems.api as lems

import xml.etree.ElementTree as ET

import re

import sys

def update_metadata(element, metadata, about_id, urn):
    
    template = '\n            <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:bqbiol="http://biomodels.net/biology-qualifiers/">\n'+\
    '                <rdf:Description rdf:about="%s">\n'+\
    '                    <bqmodel:isDescribedBy>\n'+\
    '                        <rdf:Bag>\n'+\
    '                            <rdf:li rdf:resource="%s"/>\n'+\
    '                        </rdf:Bag>\n'+\
    '                    </bqmodel:isDescribedBy>\n'+\
    '                </rdf:Description>\n'+\
    '            </rdf:RDF>\n'
    
    annotation = neuroml.Annotation()
    element.annotation = annotation
    metadata = metadata + template%(about_id, urn)
    return metadata

def channelpedia_xml_to_neuroml2(cpd_xml, nml2_file_name):
    
    print('Converting Channelpedia XML to NeuroML2')
    
    root = ET.fromstring(cpd_xml)
        
    channel_id='Channelpedia_%s_%s'%(root.attrib['ModelName'].replace("/","_"), root.attrib['ModelID'])
    
    doc = neuroml.NeuroMLDocument()
    
    metadata = ''
    
    ion = root.findall('Ion')[0]
    chan = neuroml.IonChannelHH(id=channel_id,
                          conductance='10pS',
                          species=ion.attrib['Name'],
                          notes="This is an automated conversion to NeuroML 2 of an ion channel model from Channelpedia. "
                          "\nThe original model can be found at: http://channelpedia.epfl.ch/ionchannels/%s"%root.attrib['ID'])
    
    for reference in root.findall('Reference'):
        pmid = reference.attrib['PubmedID']
        metadata = update_metadata(chan, metadata, channel_id, "urn:miriam:pubmed:%s"%pmid)
                          
    comp_types = {}
    for gate in root.findall('Gates'):
        
        eq_type = gate.attrib['EqType']
        
        if eq_type == '1':
            gate_type= 'gateHHtauInf'
            g = neuroml.GateHHTauInf(id=gate.attrib['Name'],instances=int(float(gate.attrib['Power'])), type=gate_type)
        elif eq_type == '2':
            gate_type= 'gateHHrates'
            g = neuroml.GateHHRates(id=gate.attrib['Name'],instances=int(float(gate.attrib['Power'])), type=gate_type)
        
        for inf in gate.findall('Inf_Alpha'):
            equation = check_equation(inf.findall('Equation')[0].text)
            
            if eq_type == '1':
                new_comp_type = "%s_%s"%(channel_id, 'inf')
                g.steady_state = neuroml.HHVariable(type=new_comp_type)

                comp_type = lems.ComponentType(new_comp_type, extends="baseVoltageDepVariable")

                comp_type.add(lems.Constant('TIME_SCALE', '1 ms', 'time'))
                comp_type.add(lems.Constant('VOLT_SCALE', '1 mV', 'voltage'))

                comp_type.dynamics.add(lems.DerivedVariable(name='x', dimension="none", value="%s"%equation, exposure="x"))
                comp_type.dynamics.add(lems.DerivedVariable(name='V', dimension="none", value="v / VOLT_SCALE"))

                comp_types[new_comp_type] = comp_type
                
            elif eq_type == '2':
                new_comp_type = "%s_%s"%(channel_id, 'alpha')
                g.forward_rate = neuroml.HHRate(type=new_comp_type)

                comp_type = lems.ComponentType(new_comp_type, extends="baseVoltageDepRate")

                comp_type.add(lems.Constant('TIME_SCALE', '1 ms', 'time'))
                comp_type.add(lems.Constant('VOLT_SCALE', '1 mV', 'voltage'))

                comp_type.dynamics.add(lems.DerivedVariable(name='r', dimension="per_time", value="%s / TIME_SCALE"%equation, exposure="r"))
                comp_type.dynamics.add(lems.DerivedVariable(name='V', dimension="none", value="v / VOLT_SCALE"))

                comp_types[new_comp_type] = comp_type
                
            
        for tau in gate.findall('Tau_Beta'):
            equation = check_equation(tau.findall('Equation')[0].text)
            
            if eq_type == '1':
                new_comp_type = "%s_tau"%(channel_id)
                g.time_course = neuroml.HHTime(type=new_comp_type)

                comp_type = lems.ComponentType(new_comp_type, extends="baseVoltageDepTime")

                comp_type.add(lems.Constant('TIME_SCALE', '1 ms', 'time'))
                comp_type.add(lems.Constant('VOLT_SCALE', '1 mV', 'voltage'))

                comp_type.dynamics.add(lems.DerivedVariable(name='t', dimension="none", value="(%s) * TIME_SCALE"%equation, exposure="t"))
                comp_type.dynamics.add(lems.DerivedVariable(name='V', dimension="none", value="v / VOLT_SCALE"))

                comp_types[new_comp_type] = comp_type
                
            elif eq_type == '2':
                new_comp_type = "%s_%s"%(channel_id, 'beta')
                g.reverse_rate = neuroml.HHRate(type=new_comp_type)

                comp_type = lems.ComponentType(new_comp_type, extends="baseVoltageDepRate")

                comp_type.add(lems.Constant('TIME_SCALE', '1 ms', 'time'))
                comp_type.add(lems.Constant('VOLT_SCALE', '1 mV', 'voltage'))

                comp_type.dynamics.add(lems.DerivedVariable(name='r', dimension="per_time", value="%s  / TIME_SCALE"%equation, exposure="r"))
                comp_type.dynamics.add(lems.DerivedVariable(name='V', dimension="none", value="v / VOLT_SCALE"))

                comp_types[new_comp_type] = comp_type
        
        chan.gates.append(g)
                          

    doc.ion_channel_hhs.append(chan)

    doc.id = channel_id

    writers.NeuroMLWriter.write(doc,nml2_file_name)

    print("Written NeuroML 2 channel file to: "+nml2_file_name)

    for comp_type_name in comp_types.keys():
        comp_type = comp_types[comp_type_name]
        ct_xml = comp_type.toxml()
        
        # Quick & dirty pretty printing..
        ct_xml = ct_xml.replace('<Const','\n        <Const')
        ct_xml = ct_xml.replace('<Dyna','\n        <Dyna')
        ct_xml = ct_xml.replace('</Dyna','\n        </Dyna')
        ct_xml = ct_xml.replace('<Deriv','\n            <Deriv')
        ct_xml = ct_xml.replace('</Compone','\n    </Compone')
        
        print("Adding definition for %s:\n%s\n"%(comp_type_name, ct_xml))
        nml2_file = open(nml2_file_name, 'r')
        orig = nml2_file.read()
        new_contents = orig.replace("</neuroml>", "\n    %s\n\n</neuroml>"%ct_xml)
        nml2_file.close()
        nml2_file = open(nml2_file_name, 'w')
        nml2_file.write(new_contents)
        nml2_file.close()
        
    if len(metadata)>0:
        print("Inserting metadata: %s"%metadata)
        nml2_file = open(nml2_file_name, 'r')
        orig = nml2_file.read()
        new_contents = orig.replace("<annotation/>", "\n        <annotation>%s        </annotation>\n"%metadata)
        nml2_file.close()
        nml2_file = open(nml2_file_name, 'w')
        nml2_file.write(new_contents)
        nml2_file.close()
        

    ###### Validate the NeuroML ######    

    from neuroml.utils import validate_neuroml2

    validate_neuroml2(nml2_file_name)
    
def check_equation(eqn):
    eqn = eqn.replace("v", "V")
    eqn = eqn.replace("- -", "+")
    return eqn



if __name__ == '__main__':
    if len(sys.argv) == 2:
        target = sys.argv[1]
    else:
        target = 'HCN1'
    test_file = target+'.xml'
    contents = open(test_file, 'r').read()
    channelpedia_xml_to_neuroml2(contents, target+'.channel.nml')


